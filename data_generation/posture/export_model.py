"""
Export trained posture classification model to ONNX and TorchScript
for DGX Spark deployment.
"""

import os
import argparse

import torch

from train import PostureClassifier, NUM_CLASSES


def export_onnx(checkpoint_path, output_path):
    """Export PyTorch model to ONNX format."""
    model = PostureClassifier(num_classes=NUM_CLASSES, pretrained=False)
    checkpoint = torch.load(checkpoint_path, map_location="cpu")

    if "model_state_dict" in checkpoint:
        model.load_state_dict(checkpoint["model_state_dict"])
    else:
        model.load_state_dict(checkpoint)

    model.eval()

    # Dummy input: (batch, 3, 224, 224)
    dummy_input = torch.randn(1, 3, 224, 224)

    torch.onnx.export(
        model,
        dummy_input,
        output_path,
        input_names=["image"],
        output_names=["logits"],
        dynamic_axes={
            "image": {0: "batch_size"},
            "logits": {0: "batch_size"},
        },
        opset_version=17,
    )

    print(f"ONNX model exported (initial): {output_path}")

    # Force single-file format (remove external .data dependency)
    import onnx
    from onnx.external_data_helper import convert_model_from_external_data
    onnx_model = onnx.load(output_path, load_external_data=True)
    convert_model_from_external_data(onnx_model)
    onnx.save_model(onnx_model, output_path)

    # Remove leftover .data file if exists
    data_path = output_path + ".data"
    if os.path.exists(data_path):
        os.remove(data_path)
        print(f"Removed external data file: {data_path}")

    # Verify
    onnx_model = onnx.load(output_path)
    onnx.checker.check_model(onnx_model)
    print("ONNX model validation passed (single-file)")

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"Model size: {size_mb:.2f} MB")
    if size_mb < 1.0:
        print(f"WARNING: Model is only {size_mb:.2f} MB — weights may be missing!")


def export_torchscript(checkpoint_path, output_path):
    """Export model as TorchScript for portable deployment."""
    model = PostureClassifier(num_classes=NUM_CLASSES, pretrained=False)
    checkpoint = torch.load(checkpoint_path, map_location="cpu")

    if "model_state_dict" in checkpoint:
        model.load_state_dict(checkpoint["model_state_dict"])
    else:
        model.load_state_dict(checkpoint)

    model.eval()

    dummy_input = torch.randn(1, 3, 224, 224)
    scripted = torch.jit.trace(model, dummy_input)
    scripted.save(output_path)
    print(f"TorchScript model exported: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Export posture classification model")
    parser.add_argument("--checkpoint", type=str,
                        default="/home/team-008/data/posture_model/best_model.pt")
    parser.add_argument("--output-dir", type=str,
                        default="/home/team-008/data/posture_model/exported")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # ONNX export
    onnx_path = os.path.join(args.output_dir, "posture_classifier.onnx")
    export_onnx(args.checkpoint, onnx_path)

    # TorchScript export
    ts_path = os.path.join(args.output_dir, "posture_classifier.pt")
    export_torchscript(args.checkpoint, ts_path)

    print(f"\nAll exports saved to: {args.output_dir}")


if __name__ == "__main__":
    main()
