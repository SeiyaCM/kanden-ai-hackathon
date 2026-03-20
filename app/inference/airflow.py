"""Airflow surrogate model inference using ONNX Runtime.

Replicates the input normalization from
data_generation/airflow/phase2_modulus/prepare_dataset.py (case_to_arrays).

ONNX I/O (verified via onnxruntime inspection):
  Input:  "input" -- (batch, 8) float32
  Output: "u"     -- (batch, 6) float32  [u, v, w, p, T, CO2]
          All outputs are MinMax-normalized to [0, 1].
"""

import numpy as np
import onnxruntime as ort

from app.config import AIRFLOW_MODEL_PATH, AIRFLOW_NORM
from app.inference.providers import get_providers, log_providers


def _minmax(val: float, vmin: float, vmax: float) -> float:
    r = vmax - vmin
    if r == 0:
        return 0.0
    return (val - vmin) / r


class AirflowInference:
    FIELD_NAMES = ["u", "v", "w", "p", "T", "CO2"]

    def __init__(self, model_path=None):
        path = str(model_path or AIRFLOW_MODEL_PATH)
        providers = get_providers()
        self.session = ort.InferenceSession(path, providers=providers)
        log_providers(self.session)
        self.input_name = "input"
        self.norm = AIRFLOW_NORM

    def normalize_input(
        self,
        x: float,
        y: float,
        z: float,
        ac_speed: float,
        ac_temp: float,
        window_open: float,
        layout_id: float,
        vent_rate: float,
    ) -> np.ndarray:
        """Normalize raw physical values to [0,1] model input (1, 8)."""
        n = self.norm
        return np.array(
            [[
                _minmax(x, n["coords_min"][0], n["coords_max"][0]),
                _minmax(y, n["coords_min"][1], n["coords_max"][1]),
                _minmax(z, n["coords_min"][2], n["coords_max"][2]),
                _minmax(ac_speed, n["ac_speed_min"], n["ac_speed_max"]),
                _minmax(ac_temp, n["ac_temperature_min"], n["ac_temperature_max"]),
                float(window_open),
                layout_id / 2.0,  # prepare_dataset.py line 117
                _minmax(vent_rate, n["ventilation_rate_min"], n["ventilation_rate_max"]),
            ]],
            dtype=np.float32,
        )

    def predict(self, input_array: np.ndarray) -> dict:
        """Run inference on a pre-normalized (batch, 8) input."""
        # Single output tensor "u" with shape (batch, 6): [u, v, w, p, T, CO2]
        raw = self.session.run(["u"], {self.input_name: input_array})[0]
        return {
            name: float(raw[0, i])
            for i, name in enumerate(self.FIELD_NAMES)
        }

    def predict_at_point(
        self,
        x: float,
        y: float,
        z: float,
        ac_speed: float,
        ac_temp: float,
        window_open: float,
        layout_id: float,
        vent_rate: float,
    ) -> dict:
        """Convenience: normalize raw values and run inference."""
        inp = self.normalize_input(
            x, y, z, ac_speed, ac_temp, window_open, layout_id, vent_rate
        )
        return self.predict(inp)
