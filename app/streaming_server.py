"""WebSocket streaming server — remote camera/audio from MacBook browser.

Receives JPEG frames and WebM/Opus audio from a browser client via
WebSocket, runs posture + fatigue inference on DGX Spark, and returns
results in real time.

Usage:
    python app/streaming_server.py
    → Open http://localhost:8765 in browser (via SSH port-forward)
"""

import asyncio
import base64
import json
import logging
import os
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import cv2
import numpy as np
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from app.inference.posture import PostureInference
from app.inference.airflow import AirflowInference
from app.inference.fatigue import FatigueScorer
from app.inference.audio import AudioBufferAnalyzer
from app.config import (
    ARM_SERVER_URL,
    DEFAULT_DESK_X,
    DEFAULT_DESK_Y,
    DEFAULT_DESK_Z,
    ENABLE_LLM_SCORING,
    FATIGUE_ARM_THRESHOLD,
    LLM_MODEL,
    LLM_TIMEOUT,
    LLM_WINDOW_SIZE,
    OLLAMA_HOST,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="空間AIブレイン — ストリーミングサーバー")

# ---------------------------------------------------------------------------
# Singleton models (initialized on startup)
# ---------------------------------------------------------------------------
_posture_model: PostureInference | None = None
_airflow_model: AirflowInference | None = None
_fatigue_scorer: FatigueScorer | None = None
_llm_scorer = None  # LLMFatigueScorer | None
_audio_analyzer: AudioBufferAnalyzer | None = None

# Shared state
_latest_voice_result: dict | None = None
_voice_lock = asyncio.Lock()
_latest_airflow_result: dict = {}
_arm_last_trigger: float = 0.0
_arm_cooldown: float = 30.0

# LLM async state
_llm_task: asyncio.Task | None = None
_last_llm_result: dict | None = None

# Client HTML
_CLIENT_HTML = Path(__file__).parent / "static" / "client.html"


@app.on_event("startup")
async def startup():
    global _posture_model, _airflow_model, _fatigue_scorer, _llm_scorer
    global _audio_analyzer, _latest_airflow_result

    logger.info("Loading models...")
    _posture_model = PostureInference()
    _airflow_model = AirflowInference()
    _fatigue_scorer = FatigueScorer()
    _audio_analyzer = AudioBufferAnalyzer()

    # Pre-compute default airflow result (no sensors on remote MacBook)
    _latest_airflow_result = _airflow_model.predict_at_point(
        DEFAULT_DESK_X, DEFAULT_DESK_Y, DEFAULT_DESK_Z,
        3.0, 24.0, 0.0, 0.0,  # default: ac_speed=3, temp=24, window=closed, layout=0
    )

    if ENABLE_LLM_SCORING:
        from app.inference.llm_fatigue import LLMFatigueScorer
        _llm_scorer = LLMFatigueScorer(
            ollama_host=OLLAMA_HOST,
            model_name=LLM_MODEL,
            timeout=LLM_TIMEOUT,
            window_size=LLM_WINDOW_SIZE,
        )
        logger.info("LLM scorer enabled: %s @ %s", LLM_MODEL, OLLAMA_HOST)

    logger.info("All models loaded.")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/")
async def index():
    if _CLIENT_HTML.exists():
        return HTMLResponse(_CLIENT_HTML.read_text())
    return HTMLResponse("<h1>client.html not found</h1>", status_code=404)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "llm_enabled": _llm_scorer is not None,
        "llm_available": _llm_scorer.is_available() if _llm_scorer else False,
    }


# ---------------------------------------------------------------------------
# Video WebSocket
# ---------------------------------------------------------------------------
@app.websocket("/ws/video")
async def video_endpoint(ws: WebSocket):
    await ws.accept()
    logger.info("[video] Client connected")

    frame_count = 0
    loop = asyncio.get_event_loop()

    try:
        async for data in ws.iter_text():
            msg = json.loads(data)
            if msg.get("type") != "frame":
                continue

            jpg_bytes = base64.b64decode(msg["frame"])
            img = cv2.imdecode(
                np.frombuffer(jpg_bytes, dtype=np.uint8), cv2.IMREAD_COLOR
            )
            if img is None:
                continue

            frame_count += 1
            t0 = time.monotonic()

            # Posture inference (blocking but fast ~20ms)
            posture_result = _posture_model.predict(img)

            # Fatigue scoring (LLM async or rule-based)
            fatigue_result = await _compute_fatigue(posture_result, loop)

            elapsed_ms = (time.monotonic() - t0) * 1000
            score = fatigue_result["fatigue_score"]

            # Robot arm trigger
            await _maybe_trigger_arm(score)

            await ws.send_json({
                "type": "result",
                "posture": posture_result,
                "fatigue": {
                    "fatigue_score": score,
                    "posture_score": fatigue_result.get("posture_score", 0),
                    "voice_score": fatigue_result.get("voice_score", 0),
                    "environment_score": fatigue_result.get("environment_score", 0),
                    "synergy_score": fatigue_result.get("synergy_score", 0),
                    "llm_used": fatigue_result.get("llm_used", False),
                    "llm_reasoning": fatigue_result.get("llm_reasoning", ""),
                },
                "inference_ms": round(elapsed_ms, 1),
                "frame": frame_count,
            })

            if frame_count % 30 == 0:
                logger.info(
                    "[video] frame=%d posture=%s score=%.2f %s %.0fms",
                    frame_count, posture_result["class"], score,
                    "LLM" if fatigue_result.get("llm_used") else "RULE",
                    elapsed_ms,
                )

    except WebSocketDisconnect:
        logger.info("[video] Client disconnected (frames=%d)", frame_count)


# ---------------------------------------------------------------------------
# Audio WebSocket
# ---------------------------------------------------------------------------
@app.websocket("/ws/audio")
async def audio_endpoint(ws: WebSocket):
    await ws.accept()
    logger.info("[audio] Client connected")

    chunk_count = 0
    loop = asyncio.get_event_loop()

    try:
        async for chunk in ws.iter_bytes():
            chunk_count += 1

            # Push chunk to analyzer (blocking ffmpeg decode is deferred to analyze())
            _audio_analyzer.push_chunk(chunk)

            # Run analysis every ~3 seconds (30 chunks at 100ms each)
            if chunk_count % 30 == 0:
                voice_result = await loop.run_in_executor(
                    None, _audio_analyzer.analyze
                )
                async with _voice_lock:
                    global _latest_voice_result
                    _latest_voice_result = voice_result

                await ws.send_json({"type": "voice_result", **voice_result})

                if voice_result["negative_detected"]:
                    logger.info(
                        "[audio] Negative detected: %s (score=%.2f)",
                        voice_result["matched_keywords"],
                        voice_result["voice_score"],
                    )
            else:
                await ws.send_json({"type": "audio_ack", "chunk": chunk_count})

    except WebSocketDisconnect:
        logger.info("[audio] Client disconnected (chunks=%d)", chunk_count)


# ---------------------------------------------------------------------------
# Fatigue computation (async LLM with rule-based fallback)
# ---------------------------------------------------------------------------
async def _compute_fatigue(posture_result: dict, loop) -> dict:
    global _llm_task, _last_llm_result

    async with _voice_lock:
        voice = _latest_voice_result

    if _llm_scorer is None:
        return _fatigue_scorer.compute(posture_result, _latest_airflow_result, voice)

    # Collect completed LLM result
    if _llm_task is not None and _llm_task.done():
        try:
            _last_llm_result = _llm_task.result()
        except Exception:
            pass
        _llm_task = None

    # Submit new LLM task if idle
    if _llm_task is None:
        _llm_task = asyncio.ensure_future(
            loop.run_in_executor(
                None, _llm_scorer.score,
                posture_result, _latest_airflow_result, voice,
            )
        )

    # Return cached LLM result or rule-based fallback
    if _last_llm_result is not None:
        return _last_llm_result
    return _fatigue_scorer.compute(posture_result, _latest_airflow_result, voice)


# ---------------------------------------------------------------------------
# Robot arm trigger
# ---------------------------------------------------------------------------
async def _maybe_trigger_arm(score: float) -> None:
    global _arm_last_trigger

    arm_url = os.getenv("ARM_SERVER_URL", ARM_SERVER_URL)
    if not arm_url or score < FATIGUE_ARM_THRESHOLD:
        return

    now = time.time()
    if now - _arm_last_trigger < _arm_cooldown:
        return

    _arm_last_trigger = now
    logger.info("[arm] Triggering candy delivery (score=%.2f)", score)

    try:
        import httpx
        async with httpx.AsyncClient(timeout=60.0) as client:
            await client.post(f"{arm_url}/trigger", json={"fatigue_score": score})
        logger.info("[arm] Delivery triggered successfully")
    except Exception as e:
        logger.warning("[arm] Trigger failed: %s", e)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import socket
    hostname = socket.gethostname()
    port = int(os.getenv("STREAMING_PORT", "8765"))
    print(f"\n  空間AIブレイン — ストリーミングサーバー")
    print(f"  Open in browser: http://{hostname}:{port}")
    print(f"  SSH port forward: ssh -L {port}:localhost:{port} {hostname}\n")
    uvicorn.run(app, host="0.0.0.0", port=port)
