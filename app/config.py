"""Central configuration: model paths, class labels, normalization parameters."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Model paths
# ---------------------------------------------------------------------------
POSTURE_MODEL_PATH = PROJECT_ROOT / "model" / "posture" / "posture_classifier.onnx"
AIRFLOW_MODEL_PATH = PROJECT_ROOT / "model" / "airflow" / "airflow_surrogate.onnx"

# ---------------------------------------------------------------------------
# Posture classification
# ---------------------------------------------------------------------------
POSTURE_CLASSES = ["good", "slouch", "chin_rest", "stretch"]

# ImageNet normalization (from data_generation/posture/train.py get_transforms)
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

# ---------------------------------------------------------------------------
# Airflow normalization parameters
# Derived from data_generation/airflow/phase1_cfd/room_config.py (parameter grid)
# and data_generation/airflow/phase2_modulus/prepare_dataset.py (normalization logic)
# ---------------------------------------------------------------------------
AIRFLOW_NORM = {
    # Spatial coordinates — room dimensions: 6m x 5m x 2.7m
    "coords_min": [0.0, 0.0, 0.0],
    "coords_max": [6.0, 5.0, 2.7],
    # AC speed: AC_SPEEDS = [1.0, 3.0, 5.0]
    "ac_speed_min": 1.0,
    "ac_speed_max": 5.0,
    # AC temperature: AC_TEMPS = [20.0, 24.0, 28.0]
    "ac_temperature_min": 20.0,
    "ac_temperature_max": 28.0,
    # Ventilation rate: VENTILATION_RATES = [0.0, 0.05, 0.1]
    "ventilation_rate_min": 0.0,
    "ventilation_rate_max": 0.1,
    # window_open: already binary 0/1
    # layout_id: divided by 2.0 (layouts 0,1,2 → [0, 0.5, 1.0])
}

# ---------------------------------------------------------------------------
# Default desk position (Layout 0, first desk from room_config.py)
# ---------------------------------------------------------------------------
DEFAULT_DESK_X = 1.5
DEFAULT_DESK_Y = 0.9
DEFAULT_DESK_Z = 1.2  # approximate head height when seated
