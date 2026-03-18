"""
Export trained airflow surrogate model to ONNX format for DGX Spark deployment.

The exported model can be served via TensorRT for real-time inference.
"""

import os
import argparse

import torch
import numpy as np

from train_surrogate import AirflowSurrogate


def export_onnx(checkpoint_path, output_path):
    """Export PyTorch model to ONNX format."""
    # Load model
    model = AirflowSurrogate()
    checkpoint = torch.load(checkpoint_path, map_location="cpu")

    if "model_state_dict" in checkpoint:
        model.load_state_dict(checkpoint["model_state_dict"])
    else:
        model.load_state_dict(checkpoint)

    model.eval()

    # Dummy input: (batch, 8)
    # x, y, z, ac_speed, ac_temp, window_open, layout_id, ventilation_rate
    dummy_input = torch.randn(1, 8)

    # Export
    torch.onnx.export(
        model,
        dummy_input,
        output_path,
        input_names=["input"],
        output_names=["u", "v", "w", "p", "T", "CO2"],
        dynamic_axes={
            "input": {0: "batch_size"},
            "u": {0: "batch_size"},
            "v": {0: "batch_size"},
            "w": {0: "batch_size"},
            "p": {0: "batch_size"},
            "T": {0: "batch_size"},
            "CO2": {0: "batch_size"},
        },
        opset_version=17,
    )

    print(f"ONNX model exported: {output_path}")

    # Verify
    import onnx
    onnx_model = onnx.load(output_path)
    onnx.checker.check_model(onnx_model)
    print("ONNX model validation passed")

    # Print model size
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"Model size: {size_mb:.2f} MB")


def export_torchscript(checkpoint_path, output_path):
    """Export model as TorchScript for portable deployment."""
    model = AirflowSurrogate()
    checkpoint = torch.load(checkpoint_path, map_location="cpu")

    if "model_state_dict" in checkpoint:
        model.load_state_dict(checkpoint["model_state_dict"])
    else:
        model.load_state_dict(checkpoint)

    model.eval()

    scripted = torch.jit.script(model)
    scripted.save(output_path)
    print(f"TorchScript model exported: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Export airflow surrogate model")
    parser.add_argument("--checkpoint", type=str,
                        default="/home/team-008/data/airflow_model/best_model.pt")
    parser.add_argument("--output-dir", type=str,
                        default="/home/team-008/data/airflow_model/exported")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # ONNX export
    onnx_path = os.path.join(args.output_dir, "airflow_surrogate.onnx")
    export_onnx(args.checkpoint, onnx_path)

    # TorchScript export
    ts_path = os.path.join(args.output_dir, "airflow_surrogate.pt")
    export_torchscript(args.checkpoint, ts_path)

    print(f"\nAll exports saved to: {args.output_dir}")


if __name__ == "__main__":
    main()
