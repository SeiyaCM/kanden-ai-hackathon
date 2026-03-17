"""
Validate the trained airflow surrogate model against CFD ground truth.

Computes error metrics (RMSE, relative L2 error, max error) per field
on the held-out test set and generates validation plots.
"""

import os
import json
import argparse

import numpy as np
import torch
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from train_surrogate import AirflowSurrogate, AirflowDataset


FIELD_NAMES = ["u", "v", "w", "p", "T", "CO2"]


def compute_metrics(predictions, targets):
    """Compute error metrics per field."""
    metrics = {}
    for i, name in enumerate(FIELD_NAMES):
        pred = predictions[:, i]
        true = targets[:, i]
        diff = pred - true

        rmse = np.sqrt(np.mean(diff ** 2))
        mae = np.mean(np.abs(diff))
        true_norm = np.sqrt(np.mean(true ** 2))
        rel_l2 = np.sqrt(np.mean(diff ** 2)) / max(true_norm, 1e-10)
        max_err = np.max(np.abs(diff))

        metrics[name] = {
            "rmse": float(rmse),
            "mae": float(mae),
            "relative_l2": float(rel_l2),
            "max_error": float(max_err),
        }

    return metrics


def plot_scatter(predictions, targets, output_dir):
    """Generate scatter plots of predicted vs true values per field."""
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    axes = axes.flatten()

    for i, (name, ax) in enumerate(zip(FIELD_NAMES, axes)):
        pred = predictions[:, i]
        true = targets[:, i]

        # Subsample for plotting
        n = min(10000, len(pred))
        idx = np.random.choice(len(pred), n, replace=False)

        ax.scatter(true[idx], pred[idx], alpha=0.1, s=1)
        lim = [min(true[idx].min(), pred[idx].min()),
               max(true[idx].max(), pred[idx].max())]
        ax.plot(lim, lim, "r--", linewidth=1)
        ax.set_xlabel(f"CFD ({name})")
        ax.set_ylabel(f"Predicted ({name})")
        ax.set_title(name)
        ax.set_aspect("equal")

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "validation_scatter.png"), dpi=150)
    plt.close()
    print(f"Scatter plot saved: {output_dir}/validation_scatter.png")


def plot_error_distribution(predictions, targets, output_dir):
    """Generate error distribution histograms per field."""
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    axes = axes.flatten()

    for i, (name, ax) in enumerate(zip(FIELD_NAMES, axes)):
        errors = predictions[:, i] - targets[:, i]
        ax.hist(errors, bins=100, density=True, alpha=0.7)
        ax.set_xlabel(f"Error ({name})")
        ax.set_ylabel("Density")
        ax.set_title(f"{name} error distribution")
        ax.axvline(0, color="r", linestyle="--", linewidth=1)

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "validation_errors.png"), dpi=150)
    plt.close()
    print(f"Error distribution saved: {output_dir}/validation_errors.png")


def compute_derived_outputs(predictions):
    """Compute derived quantities from model outputs.

    - Stagnation index: 1 / (|velocity| + epsilon)
    - CO2 retention: local_CO2 / mean_CO2
    """
    u, v, w = predictions[:, 0], predictions[:, 1], predictions[:, 2]
    co2 = predictions[:, 5]

    speed = np.sqrt(u**2 + v**2 + w**2)
    stagnation = 1.0 / (speed + 1e-6)

    mean_co2 = np.mean(co2)
    co2_retention = co2 / max(mean_co2, 1e-10)

    return {
        "stagnation_index": stagnation,
        "co2_retention": co2_retention,
    }


def main():
    parser = argparse.ArgumentParser(description="Validate airflow surrogate")
    parser.add_argument("--checkpoint", type=str,
                        default="/home/team-008/data/airflow_model/best_model.pt")
    parser.add_argument("--data-path", type=str,
                        default="/home/team-008/data/cfd_dataset/prepared/test")
    parser.add_argument("--output-dir", type=str,
                        default="/home/team-008/data/airflow_model/validation")
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    os.makedirs(args.output_dir, exist_ok=True)

    # Load model
    model = AirflowSurrogate().to(device)
    checkpoint = torch.load(args.checkpoint, map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    # Load test data
    dataset = AirflowDataset(args.data_path)
    inputs = torch.tensor(dataset.inputs, dtype=torch.float32).to(device)
    targets = dataset.outputs

    # Inference
    print(f"Running inference on {len(inputs)} points...")
    with torch.no_grad():
        # Process in chunks to avoid OOM
        chunk_size = 100000
        predictions_list = []
        for i in range(0, len(inputs), chunk_size):
            chunk = inputs[i:i + chunk_size]
            pred = model(chunk).cpu().numpy()
            predictions_list.append(pred)
        predictions = np.concatenate(predictions_list, axis=0)

    # Metrics
    metrics = compute_metrics(predictions, targets)
    print("\n=== Validation Metrics ===")
    for name, m in metrics.items():
        print(f"  {name:5s}: RMSE={m['rmse']:.6f}, "
              f"RelL2={m['relative_l2']:.4f}, "
              f"MAE={m['mae']:.6f}, "
              f"MaxErr={m['max_error']:.6f}")

    metrics_path = os.path.join(args.output_dir, "metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    # Derived outputs
    derived = compute_derived_outputs(predictions)
    print(f"\nStagnation index range: "
          f"[{derived['stagnation_index'].min():.4f}, "
          f"{derived['stagnation_index'].max():.4f}]")
    print(f"CO2 retention range: "
          f"[{derived['co2_retention'].min():.4f}, "
          f"{derived['co2_retention'].max():.4f}]")

    # Plots
    plot_scatter(predictions, targets, args.output_dir)
    plot_error_distribution(predictions, targets, args.output_dir)

    print(f"\nValidation results saved to: {args.output_dir}")


if __name__ == "__main__":
    main()
