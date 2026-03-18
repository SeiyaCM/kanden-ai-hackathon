"""
Validate the trained posture classification model on the test set.

Computes per-class Accuracy, Precision, Recall, F1 and generates
a confusion matrix.
"""

import os
import json
import argparse

import numpy as np
import torch
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import classification_report, confusion_matrix

from train import PostureClassifier, PostureDataset, get_transforms, NUM_CLASSES


CLASS_NAMES = ["01_good", "02_slouch", "03_chin_rest", "04_stretch"]

DEFAULT_DATA_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "../data/synthetic_dataset")
)


def plot_confusion_matrix(cm, output_dir):
    """Generate and save a confusion matrix plot."""
    fig, ax = plt.subplots(figsize=(8, 8))
    im = ax.imshow(cm, interpolation="nearest", cmap=plt.cm.Blues)
    ax.set_title("Confusion Matrix")
    fig.colorbar(im)

    tick_marks = np.arange(len(CLASS_NAMES))
    ax.set_xticks(tick_marks)
    ax.set_xticklabels(CLASS_NAMES, rotation=45, ha="right")
    ax.set_yticks(tick_marks)
    ax.set_yticklabels(CLASS_NAMES)

    # Text annotations
    thresh = cm.max() / 2.0
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, format(cm[i, j], "d"),
                    ha="center", va="center",
                    color="white" if cm[i, j] > thresh else "black")

    ax.set_ylabel("True label")
    ax.set_xlabel("Predicted label")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "confusion_matrix.png"), dpi=150)
    plt.close()
    print(f"Confusion matrix saved: {output_dir}/confusion_matrix.png")


def main():
    parser = argparse.ArgumentParser(description="Validate posture classifier")
    parser.add_argument("--checkpoint", type=str,
                        default="/home/team-008/data/posture_model/best_model.pt")
    parser.add_argument("--data-path", type=str, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output-dir", type=str,
                        default="/home/team-008/data/posture_model/validation")
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    os.makedirs(args.output_dir, exist_ok=True)

    # Load model
    model = PostureClassifier(num_classes=NUM_CLASSES, pretrained=False).to(device)
    checkpoint = torch.load(args.checkpoint, map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    # Load test data
    test_dataset = PostureDataset(
        os.path.join(args.data_path, "test.json"),
        args.data_path,
        transform=get_transforms(is_train=False),
    )
    test_loader = torch.utils.data.DataLoader(
        test_dataset, batch_size=args.batch_size, shuffle=False,
        num_workers=4, pin_memory=True,
    )

    print(f"Running inference on {len(test_dataset)} test samples...")

    all_preds = []
    all_labels = []

    with torch.no_grad():
        for images, labels in test_loader:
            images = images.to(device)
            logits = model(images)
            preds = logits.argmax(dim=1).cpu().numpy()
            all_preds.extend(preds)
            all_labels.extend(labels.numpy())

    all_preds = np.array(all_preds)
    all_labels = np.array(all_labels)

    # Classification report
    report = classification_report(
        all_labels, all_preds,
        target_names=CLASS_NAMES,
        output_dict=True,
    )
    report_text = classification_report(
        all_labels, all_preds,
        target_names=CLASS_NAMES,
    )

    print("\n=== Classification Report ===")
    print(report_text)

    # Confusion matrix
    cm = confusion_matrix(all_labels, all_preds)
    print("Confusion Matrix:")
    print(cm)

    # Overall accuracy
    accuracy = np.mean(all_preds == all_labels)
    print(f"\nOverall Accuracy: {accuracy:.4f}")

    # Save metrics
    metrics = {
        "accuracy": float(accuracy),
        "classification_report": report,
        "confusion_matrix": cm.tolist(),
    }
    metrics_path = os.path.join(args.output_dir, "metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Metrics saved: {metrics_path}")

    # Plot
    plot_confusion_matrix(cm, args.output_dir)

    print(f"\nValidation results saved to: {args.output_dir}")


if __name__ == "__main__":
    main()
