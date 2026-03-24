"""Central configuration: model paths, class labels, normalization parameters."""

import os
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

# ---------------------------------------------------------------------------
# Speech / Voice analysis
# ---------------------------------------------------------------------------
WHISPER_MODEL_SIZE = "base"
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE_TYPE = "int8"

AUDIO_SAMPLE_RATE = 16000
AUDIO_BUFFER_SECONDS = 5
AUDIO_ANALYZE_INTERVAL = 3  # seconds between transcription runs

VOICE_SCORE_DECAY = 0.85  # per-cycle decay when no negative speech detected

NEGATIVE_KEYWORDS: dict[str, float] = {
    "疲れた": 0.9,
    "しんどい": 0.9,
    "眠い": 0.7,
    "眠たい": 0.7,
    "だるい": 0.8,
    "つらい": 0.8,
    "わからない": 0.5,
    "無理": 0.7,
    "きつい": 0.8,
    "集中できない": 0.6,
    "頭痛い": 0.8,
}

# ---------------------------------------------------------------------------
# LLM Fatigue Scorer (Ollama)
# ---------------------------------------------------------------------------
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3:8b")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "5.0"))
LLM_WINDOW_SIZE = int(os.getenv("LLM_WINDOW_SIZE", "5"))
ENABLE_LLM_SCORING = os.getenv("ENABLE_LLM_SCORING", "true").lower() == "true"

# ---------------------------------------------------------------------------
# Robot arm trigger (SO-ARM101)
# ---------------------------------------------------------------------------
ARM_SERVER_URL = os.getenv("ARM_SERVER_URL", "http://localhost:8766")
FATIGUE_ARM_THRESHOLD = float(os.getenv("FATIGUE_ARM_THRESHOLD", "0.7"))
