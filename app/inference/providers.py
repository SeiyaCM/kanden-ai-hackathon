"""ONNX Runtime execution provider selection.

Priority order is determined by the ONNX_DEVICE environment variable:
  - "dgx"  → TensorRT > CUDA > CPU   (for NVIDIA DGX Spark)
  - "cuda" → CUDA > CPU              (generic CUDA machine)
  - "cpu"  → CPU only                (forced CPU, useful for debugging)
  - unset  → TensorRT > CUDA > CPU   (auto-detect from available providers)
"""

import os

import onnxruntime as ort


def get_providers() -> list[str]:
    """Return the filtered, ordered list of ORT execution providers."""
    device = os.environ.get("ONNX_DEVICE", "auto").lower()
    available = ort.get_available_providers()

    if device == "cpu":
        candidates = ["CPUExecutionProvider"]
    elif device == "cuda":
        candidates = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    else:
        # "dgx" or "auto": prefer TensorRT, fall back gracefully
        candidates = [
            "TensorrtExecutionProvider",
            "CUDAExecutionProvider",
            "CPUExecutionProvider",
        ]

    return [p for p in candidates if p in available]


def log_providers(session: ort.InferenceSession) -> None:
    """Print the providers actually used by a session."""
    active = session.get_providers()
    print(f"[ORT] Active providers: {active}")
