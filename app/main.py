"""空間AIブレイン — 疲労度モニター (Streamlit demo).

Usage:
    streamlit run app/main.py
"""

import os
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path so "app" package is importable
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import cv2
import numpy as np
import requests
import streamlit as st
from PIL import ImageFont, ImageDraw, Image

from app.inference.posture import PostureInference
from app.inference.airflow import AirflowInference
from app.inference.fatigue import FatigueScorer
from app.config import (
    AUDIO_ANALYZE_INTERVAL,
    DEFAULT_DESK_X,
    DEFAULT_DESK_Y,
    DEFAULT_DESK_Z,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="空間AIブレイン", layout="wide")
st.title("空間AIブレイン — 疲労度モニター")

# ---------------------------------------------------------------------------
# Load models (cached across reruns)
# ---------------------------------------------------------------------------

@st.cache_resource
def load_models():
    return PostureInference(), AirflowInference(), FatigueScorer()


posture_model, airflow_model, fatigue_scorer = load_models()


@st.cache_resource
def load_audio_analyzer():
    """Load AudioSpeechAnalyzer; returns None if mic unavailable."""
    try:
        from app.inference.audio import AudioSpeechAnalyzer
        return AudioSpeechAnalyzer()
    except Exception:
        return None

# ---------------------------------------------------------------------------
# Sidebar — room environment controls
# ---------------------------------------------------------------------------
st.sidebar.header("室内環境設定")
ac_speed = st.sidebar.slider("エアコン風速 (m/s)", 1.0, 5.0, 3.0, 0.5)
ac_temp = st.sidebar.slider("エアコン温度 (°C)", 20.0, 28.0, 24.0, 1.0)
window_open = st.sidebar.checkbox("窓を開ける", value=False)
layout_id = st.sidebar.selectbox("家具レイアウト", [0, 1, 2])

st.sidebar.header("デスク位置")
desk_x = st.sidebar.number_input("X (m)", 0.0, 6.0, DEFAULT_DESK_X, 0.1)
desk_y = st.sidebar.number_input("Y (m)", 0.0, 5.0, DEFAULT_DESK_Y, 0.1)
desk_z = st.sidebar.number_input("Z (m)", 0.0, 2.7, DEFAULT_DESK_Z, 0.1)

# ---------------------------------------------------------------------------
# Sidebar — voice monitoring
# ---------------------------------------------------------------------------
st.sidebar.header("音声設定")
enable_voice = st.sidebar.checkbox("音声モニタリング", value=True)
audio_analyzer = load_audio_analyzer() if enable_voice else None
if enable_voice and audio_analyzer is None:
    st.sidebar.warning("マイク未検出 — 音声モニタリング無効")

# ---------------------------------------------------------------------------
# Sidebar — optional cloud send
# ---------------------------------------------------------------------------
st.sidebar.header("クラウド連携")
send_to_cloud = st.sidebar.checkbox("API Gatewayに送信", value=False)
api_url = st.sidebar.text_input("API URL", value=os.getenv("FATIGUE_API_URL", ""))
api_key = st.sidebar.text_input(
    "API Key", value=os.getenv("FATIGUE_API_KEY", ""), type="password"
)

# ---------------------------------------------------------------------------
# Airflow inference (runs once per slider change)
# ---------------------------------------------------------------------------
airflow_result = airflow_model.predict_at_point(
    desk_x, desk_y, desk_z,
    ac_speed, ac_temp, float(window_open), float(layout_id)
)

# ---------------------------------------------------------------------------
# Camera feed + posture inference
# ---------------------------------------------------------------------------
POSTURE_LABELS_JA = {
    "good": "良好",
    "slouch": "猫背",
    "chin_rest": "頬杖",
    "stretch": "ストレッチ",
}

FATIGUE_COLORS = {
    "low": (0, 200, 0),       # green
    "medium": (0, 200, 255),   # orange (BGR)
    "high": (0, 0, 255),       # red
}


def fatigue_color(score: float):
    if score < 0.3:
        return FATIGUE_COLORS["low"]
    if score < 0.6:
        return FATIGUE_COLORS["medium"]
    return FATIGUE_COLORS["high"]


def _get_font(size: int = 20) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a Japanese-capable font, falling back to PIL default."""
    # Windows: Yu Gothic / Meiryo, Linux: Noto Sans CJK
    candidates = [
        "C:/Windows/Fonts/yugothib.ttf",
        "C:/Windows/Fonts/meiryo.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


@st.cache_resource
def load_font():
    return _get_font(20)


def draw_overlay(frame, posture_result, fatigue_result):
    """Draw posture label and fatigue score on the frame (supports Japanese)."""
    h, w = frame.shape[:2]
    cls = posture_result["class"]
    label_ja = POSTURE_LABELS_JA.get(cls, cls)
    conf = posture_result["confidence"]
    score = fatigue_result["fatigue_score"]
    color_bgr = fatigue_color(score)
    # PIL uses RGB
    color_rgb = (color_bgr[2], color_bgr[1], color_bgr[0])

    # Background rectangle (still via cv2 for speed)
    cv2.rectangle(frame, (0, 0), (w, 60), (0, 0, 0), -1)

    # Convert to PIL for Japanese text rendering
    pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)
    font = load_font()

    draw.text((10, 5), f"姿勢: {label_ja} ({conf:.0%})", fill=(255, 255, 255), font=font)
    draw.text((10, 32), f"疲労度: {score:.2f}", fill=color_rgb, font=font)

    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


col_cam, col_dash = st.columns([3, 2])

with col_dash:
    st.subheader("疲労度ダッシュボード")
    score_placeholder = st.empty()
    posture_placeholder = st.empty()

    st.subheader("音声認識")
    voice_text_placeholder = st.empty()
    voice_status_placeholder = st.empty()

    st.subheader("室内環境 (AI予測)")
    env_placeholder = st.empty()
    env_placeholder.json(airflow_result)

camera_placeholder = col_cam.empty()

# ---------------------------------------------------------------------------
# Main camera loop
# ---------------------------------------------------------------------------
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    st.warning("カメラが検出されません。Webカメラを接続してください。")
    st.stop()

INFERENCE_INTERVAL = 5  # run posture inference every N frames
frame_count = 0
last_posture = {"class": "good", "class_idx": 0, "confidence": 0.0, "probabilities": {}}
last_fatigue = {"fatigue_score": 0.0, "posture_score": 0.0, "environment_score": 0.0}
last_voice_result: dict | None = None
last_voice_analyze = 0.0
cloud_send_interval = 10.0  # seconds
last_cloud_send = 0.0

try:
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1

        # Run voice analysis periodically
        now = time.time()
        if audio_analyzer and now - last_voice_analyze > AUDIO_ANALYZE_INTERVAL:
            last_voice_analyze = now
            last_voice_result = audio_analyzer.analyze()

            voice_text_placeholder.text(
                f"認識テキスト: {last_voice_result['transcript'] or '（音声なし）'}"
            )
            if last_voice_result["negative_detected"]:
                voice_status_placeholder.warning(
                    f"⚠ ネガティブ発話検出: "
                    f"{', '.join(last_voice_result['matched_keywords'])}"
                )
            else:
                voice_status_placeholder.info("音声: 正常")

        # Run posture inference periodically
        if frame_count % INFERENCE_INTERVAL == 0:
            last_posture = posture_model.predict(frame)
            last_fatigue = fatigue_scorer.compute(
                last_posture, airflow_result, last_voice_result
            )

            # Update dashboard
            score = last_fatigue["fatigue_score"]
            score_placeholder.metric(
                "総合疲労スコア",
                f"{score:.2f}",
                delta=None,
            )
            posture_placeholder.markdown(
                f"**姿勢**: {POSTURE_LABELS_JA.get(last_posture['class'], last_posture['class'])} "
                f"(信頼度 {last_posture['confidence']:.0%})"
            )

            # Optional cloud send
            now = time.time()
            if (
                send_to_cloud
                and api_url
                and api_key
                and now - last_cloud_send > cloud_send_interval
            ):
                last_cloud_send = now
                payload = {
                    "device_id": "dgx-spark-001",
                    "user_id": "engineer-001",
                    "timestamp": last_fatigue["timestamp"],
                    "fatigue_score": score,
                    "modalities": {
                        "camera": {
                            "score": last_fatigue["posture_score"],
                            "detected_posture": last_posture["class"],
                        },
                        "voice": {
                            "score": last_fatigue.get("voice_score", 0.0),
                            "negative_detected": (
                                last_voice_result.get("negative_detected", False)
                                if last_voice_result
                                else False
                            ),
                        },
                    },
                }
                try:
                    requests.post(
                        api_url,
                        json=payload,
                        headers={"x-api-key": api_key},
                        timeout=3,
                    )
                except requests.RequestException:
                    pass  # fire-and-forget

        # Draw overlay and display
        display = draw_overlay(frame.copy(), last_posture, last_fatigue)
        camera_placeholder.image(
            cv2.cvtColor(display, cv2.COLOR_BGR2RGB),
            channels="RGB",
            use_container_width=True,
        )

finally:
    cap.release()
    if audio_analyzer:
        audio_analyzer.stop()
