"""Posture classification inference using ONNX Runtime.

Replicates the eval-time preprocessing from data_generation/posture/train.py:
  Resize(224,224) → ToTensor → Normalize(ImageNet)

ONNX I/O (from data_generation/posture/export_model.py):
  Input:  "image"  — (batch, 3, 224, 224) float32
  Output: "logits" — (batch, 4) float32
"""

import numpy as np
import onnxruntime as ort
import cv2

from app.config import POSTURE_MODEL_PATH, POSTURE_CLASSES, IMAGENET_MEAN, IMAGENET_STD
from app.inference.providers import get_providers, log_providers


class PostureInference:
    def __init__(self, model_path=None):
        path = str(model_path or POSTURE_MODEL_PATH)
        providers = get_providers()
        self.session = ort.InferenceSession(path, providers=providers)
        log_providers(self.session)
        self.input_name = "image"
        self.output_name = "logits"
        self._mean = np.array(IMAGENET_MEAN, dtype=np.float32).reshape(3, 1, 1)
        self._std = np.array(IMAGENET_STD, dtype=np.float32).reshape(3, 1, 1)

    def preprocess(self, bgr_frame: np.ndarray) -> np.ndarray:
        """BGR frame (H,W,3 uint8) → (1, 3, 224, 224) float32."""
        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (224, 224))
        tensor = resized.astype(np.float32) / 255.0
        tensor = tensor.transpose(2, 0, 1)  # HWC → CHW
        tensor = (tensor - self._mean) / self._std
        return tensor[np.newaxis, ...]  # add batch dim

    @staticmethod
    def softmax(logits: np.ndarray) -> np.ndarray:
        exp = np.exp(logits - np.max(logits, axis=-1, keepdims=True))
        return exp / exp.sum(axis=-1, keepdims=True)

    def predict(self, bgr_frame: np.ndarray) -> dict:
        """Run inference on a single BGR frame.

        Returns dict with keys: class, class_idx, confidence, probabilities.
        """
        input_tensor = self.preprocess(bgr_frame)
        logits = self.session.run(
            [self.output_name], {self.input_name: input_tensor}
        )[0]
        probs = self.softmax(logits)[0]
        class_idx = int(np.argmax(probs))
        return {
            "class": POSTURE_CLASSES[class_idx],
            "class_idx": class_idx,
            "confidence": float(probs[class_idx]),
            "probabilities": {
                name: float(p) for name, p in zip(POSTURE_CLASSES, probs)
            },
        }
