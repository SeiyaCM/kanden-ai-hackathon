"""
Train a posture classification model (ResNet18) for fatigue detection.

The model classifies synthetic engineer images into 4 posture classes:
  01_good (0), 02_slouch (1), 03_chin_rest (2), 04_stretch (3)

Input:  RGB image (3, 224, 224)
Output: class logits (4,)
"""

import os
import json
import argparse

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms, models
from PIL import Image


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../data/synthetic_dataset"))
NUM_CLASSES = 4


class PostureDataset(Dataset):
    """Dataset for posture classification from synthetic images."""

    def __init__(self, split_json, image_dir, transform=None):
        with open(split_json, "r", encoding="utf-8") as f:
            self.records = json.load(f)
        self.image_dir = image_dir
        self.transform = transform

    def __len__(self):
        return len(self.records)

    def __getitem__(self, idx):
        record = self.records[idx]
        img_path = os.path.join(self.image_dir, record["file_name"])
        image = Image.open(img_path).convert("RGB")

        if self.transform:
            image = self.transform(image)

        label = record["label_id"]
        return image, label


class PostureClassifier(nn.Module):
    """ResNet18-based classifier for posture/fatigue detection."""

    def __init__(self, num_classes=NUM_CLASSES, pretrained=True):
        super().__init__()
        weights = models.ResNet18_Weights.DEFAULT if pretrained else None
        self.backbone = models.resnet18(weights=weights)
        in_features = self.backbone.fc.in_features
        self.backbone.fc = nn.Linear(in_features, num_classes)

    def forward(self, x):
        return self.backbone(x)


def get_transforms(is_train=True):
    """Get image transforms for training or evaluation."""
    if is_train:
        return transforms.Compose([
            transforms.Resize((256, 256)),
            transforms.RandomCrop(224),
            transforms.RandomHorizontalFlip(),
            transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                 std=[0.229, 0.224, 0.225]),
        ])
    else:
        return transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                 std=[0.229, 0.224, 0.225]),
        ])


def train(args):
    """Main training loop."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    # Datasets
    train_dataset = PostureDataset(
        os.path.join(args.data_path, "train.json"),
        args.data_path,
        transform=get_transforms(is_train=True),
    )
    val_dataset = PostureDataset(
        os.path.join(args.data_path, "val.json"),
        args.data_path,
        transform=get_transforms(is_train=False),
    )

    print(f"Train samples: {len(train_dataset)}, Val samples: {len(val_dataset)}")

    train_loader = DataLoader(
        train_dataset, batch_size=args.batch_size, shuffle=True,
        num_workers=4, pin_memory=True,
    )
    val_loader = DataLoader(
        val_dataset, batch_size=args.batch_size, shuffle=False,
        num_workers=4, pin_memory=True,
    )

    # Model
    model = PostureClassifier(num_classes=NUM_CLASSES, pretrained=True).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=args.epochs, eta_min=1e-6
    )
    criterion = nn.CrossEntropyLoss()

    os.makedirs(args.output_dir, exist_ok=True)

    best_val_loss = float("inf")
    best_val_acc = 0.0
    history = []

    for epoch in range(args.epochs):
        # Training
        model.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0

        for images, labels in train_loader:
            images = images.to(device)
            labels = labels.to(device)

            logits = model(images)
            loss = criterion(logits, labels)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            train_loss += loss.item()
            train_correct += (logits.argmax(dim=1) == labels).sum().item()
            train_total += labels.size(0)

        scheduler.step()

        train_loss /= len(train_loader)
        train_acc = train_correct / train_total

        # Validation
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0

        with torch.no_grad():
            for images, labels in val_loader:
                images = images.to(device)
                labels = labels.to(device)

                logits = model(images)
                loss = criterion(logits, labels)

                val_loss += loss.item()
                val_correct += (logits.argmax(dim=1) == labels).sum().item()
                val_total += labels.size(0)

        val_loss /= max(len(val_loader), 1)
        val_acc = val_correct / max(val_total, 1)

        # Logging
        lr = optimizer.param_groups[0]["lr"]
        print(f"Epoch {epoch + 1:4d}/{args.epochs} | "
              f"train_loss={train_loss:.4f} acc={train_acc:.4f} | "
              f"val_loss={val_loss:.4f} acc={val_acc:.4f} | "
              f"lr={lr:.2e}")

        history.append({
            "epoch": epoch + 1,
            "train_loss": train_loss,
            "train_acc": train_acc,
            "val_loss": val_loss,
            "val_acc": val_acc,
            "lr": lr,
        })

        # Save best model
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_val_acc = val_acc
            torch.save({
                "epoch": epoch + 1,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "val_loss": val_loss,
                "val_acc": val_acc,
            }, os.path.join(args.output_dir, "best_model.pt"))

        # Periodic checkpoint
        if (epoch + 1) % 10 == 0:
            torch.save({
                "epoch": epoch + 1,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "val_loss": val_loss,
                "val_acc": val_acc,
            }, os.path.join(args.output_dir, f"checkpoint_epoch{epoch + 1}.pt"))

    # Save training history
    with open(os.path.join(args.output_dir, "training_history.json"), "w") as f:
        json.dump(history, f, indent=2)

    # Save final model
    torch.save(model.state_dict(), os.path.join(args.output_dir, "final_model.pt"))

    print(f"\nTraining complete. Best val_loss: {best_val_loss:.4f}, "
          f"Best val_acc: {best_val_acc:.4f}")
    print(f"Models saved to: {args.output_dir}")


def parse_args():
    parser = argparse.ArgumentParser(description="Train posture classification model")
    parser.add_argument("--data-path", type=str, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output-dir", type=str,
                        default="/home/team-008/data/posture_model")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-4)
    return parser.parse_args()


if __name__ == "__main__":
    train(parse_args())
