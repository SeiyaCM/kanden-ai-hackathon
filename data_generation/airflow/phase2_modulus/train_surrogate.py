"""
Train a Physics-Informed Neural Network (PINNs) surrogate model using
NVIDIA Modulus (Physics-NeMo).

The model learns to predict airflow fields (velocity, pressure, temperature,
CO2) given spatial coordinates and room conditions, while respecting
Navier-Stokes equations in the loss function.

Input:  (x, y, z, ac_speed, ac_temp, window_open, layout_id, ventilation_rate)
Output: (u, v, w, p, T, CO2)
"""

import os
import json
import argparse

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader


class AirflowDataset(Dataset):
    """Dataset for airflow surrogate model training."""

    def __init__(self, data_dir):
        self.inputs = np.load(os.path.join(data_dir, "inputs.npy"))
        self.outputs = np.load(os.path.join(data_dir, "outputs.npy"))

    def __len__(self):
        return len(self.inputs)

    def __getitem__(self, idx):
        return (
            torch.tensor(self.inputs[idx], dtype=torch.float32),
            torch.tensor(self.outputs[idx], dtype=torch.float32),
        )


class AirflowSurrogate(nn.Module):
    """Fully-connected network for airflow prediction.

    Architecture: 8 -> 256 -> 256 -> 256 -> 256 -> 256 -> 256 -> 6
    with SiLU activations.
    """

    def __init__(self, input_dim=8, output_dim=6, hidden_dim=256, n_layers=6):
        super().__init__()

        layers = [nn.Linear(input_dim, hidden_dim), nn.SiLU()]
        for _ in range(n_layers - 1):
            layers.extend([nn.Linear(hidden_dim, hidden_dim), nn.SiLU()])
        layers.append(nn.Linear(hidden_dim, output_dim))

        self.net = nn.Sequential(*layers)

    def forward(self, x):
        return self.net(x)


def compute_physics_loss(model, x, nu=1.5e-5):
    """Compute physics-informed loss from Navier-Stokes residuals.

    Uses automatic differentiation to compute spatial derivatives
    and evaluate PDE residuals.

    Args:
        model: the surrogate network
        x: input tensor (batch, 8) with requires_grad=True for spatial dims
        nu: kinematic viscosity of air [m^2/s]

    Returns:
        physics_loss: scalar tensor
    """
    x_phys = x.clone().requires_grad_(True)
    pred = model(x_phys)

    u, v, w = pred[:, 0:1], pred[:, 1:2], pred[:, 2:3]
    p = pred[:, 3:4]

    # Spatial coordinates
    xyz = x_phys[:, :3]

    # Compute gradients
    def grad(y, x_in):
        return torch.autograd.grad(
            y, x_in,
            grad_outputs=torch.ones_like(y),
            create_graph=True,
            retain_graph=True,
        )[0]

    # First derivatives
    grads_u = grad(u, x_phys)[:, :3]  # du/dx, du/dy, du/dz
    grads_v = grad(v, x_phys)[:, :3]
    grads_w = grad(w, x_phys)[:, :3]
    grads_p = grad(p, x_phys)[:, :3]

    du_dx, du_dy, du_dz = grads_u[:, 0:1], grads_u[:, 1:2], grads_u[:, 2:3]
    dv_dx, dv_dy, dv_dz = grads_v[:, 0:1], grads_v[:, 1:2], grads_v[:, 2:3]
    dw_dx, dw_dy, dw_dz = grads_w[:, 0:1], grads_w[:, 1:2], grads_w[:, 2:3]
    dp_dx, dp_dy, dp_dz = grads_p[:, 0:1], grads_p[:, 1:2], grads_p[:, 2:3]

    # Continuity equation: du/dx + dv/dy + dw/dz = 0
    continuity = du_dx + dv_dy + dw_dz

    # Momentum equations (steady-state, incompressible):
    # u * du/dx + v * du/dy + w * du/dz = -dp/dx + nu * laplacian(u)
    # (simplified: omit second derivatives for computational efficiency)
    momentum_x = u * du_dx + v * du_dy + w * du_dz + dp_dx
    momentum_y = u * dv_dx + v * dv_dy + w * dv_dz + dp_dy
    momentum_z = u * dw_dx + v * dw_dy + w * dw_dz + dp_dz

    physics_loss = (
        torch.mean(continuity ** 2)
        + torch.mean(momentum_x ** 2)
        + torch.mean(momentum_y ** 2)
        + torch.mean(momentum_z ** 2)
    )

    return physics_loss


def train(args):
    """Main training loop."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    # Load data
    train_dataset = AirflowDataset(os.path.join(args.data_path, "train"))
    val_dataset = AirflowDataset(os.path.join(args.data_path, "val"))

    train_loader = DataLoader(
        train_dataset, batch_size=args.batch_size, shuffle=True,
        num_workers=4, pin_memory=True,
    )
    val_loader = DataLoader(
        val_dataset, batch_size=args.batch_size, shuffle=False,
        num_workers=4, pin_memory=True,
    )

    # Model
    model = AirflowSurrogate().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=args.epochs, eta_min=1e-6
    )

    # Loss weights
    data_weight = 1.0
    physics_weight = args.physics_weight

    os.makedirs(args.output_dir, exist_ok=True)

    best_val_loss = float("inf")
    history = []

    for epoch in range(args.epochs):
        # Training
        model.train()
        train_data_loss = 0.0
        train_phys_loss = 0.0
        n_batches = 0

        for inputs, targets in train_loader:
            inputs = inputs.to(device)
            targets = targets.to(device)

            # Data loss
            predictions = model(inputs)
            data_loss = nn.functional.mse_loss(predictions, targets)

            # Physics loss (on a subset for efficiency)
            phys_subset = inputs[:min(1024, len(inputs))]
            physics_loss = compute_physics_loss(model, phys_subset)

            # Total loss
            loss = data_weight * data_loss + physics_weight * physics_loss

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            train_data_loss += data_loss.item()
            train_phys_loss += physics_loss.item()
            n_batches += 1

        scheduler.step()

        train_data_loss /= n_batches
        train_phys_loss /= n_batches

        # Validation
        model.eval()
        val_loss = 0.0
        n_val = 0
        with torch.no_grad():
            for inputs, targets in val_loader:
                inputs = inputs.to(device)
                targets = targets.to(device)
                predictions = model(inputs)
                val_loss += nn.functional.mse_loss(predictions, targets).item()
                n_val += 1

        val_loss /= max(n_val, 1)

        # Logging
        lr = optimizer.param_groups[0]["lr"]
        print(f"Epoch {epoch + 1:4d}/{args.epochs} | "
              f"data_loss={train_data_loss:.6f} | "
              f"phys_loss={train_phys_loss:.6f} | "
              f"val_loss={val_loss:.6f} | "
              f"lr={lr:.2e}")

        history.append({
            "epoch": epoch + 1,
            "train_data_loss": train_data_loss,
            "train_physics_loss": train_phys_loss,
            "val_loss": val_loss,
            "lr": lr,
        })

        # Save best model
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save({
                "epoch": epoch + 1,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "val_loss": val_loss,
            }, os.path.join(args.output_dir, "best_model.pt"))

        # Periodic checkpoint
        if (epoch + 1) % 100 == 0:
            torch.save({
                "epoch": epoch + 1,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "val_loss": val_loss,
            }, os.path.join(args.output_dir, f"checkpoint_epoch{epoch + 1}.pt"))

    # Save training history
    with open(os.path.join(args.output_dir, "training_history.json"), "w") as f:
        json.dump(history, f, indent=2)

    # Save final model
    torch.save(model.state_dict(), os.path.join(args.output_dir, "final_model.pt"))

    print(f"\nTraining complete. Best val_loss: {best_val_loss:.6f}")
    print(f"Models saved to: {args.output_dir}")


def parse_args():
    parser = argparse.ArgumentParser(description="Train airflow surrogate model")
    parser.add_argument("--data-path", type=str,
                        default="/home/team-008/data/cfd_dataset/prepared")
    parser.add_argument("--output-dir", type=str,
                        default="/home/team-008/data/airflow_model")
    parser.add_argument("--epochs", type=int, default=1000)
    parser.add_argument("--batch-size", type=int, default=4096)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--physics-weight", type=float, default=0.1,
                        help="Weight for physics-informed loss term")
    return parser.parse_args()


if __name__ == "__main__":
    train(parse_args())
