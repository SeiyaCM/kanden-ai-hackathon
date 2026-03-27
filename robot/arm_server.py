"""SO-ARM101 candy delivery server — triggered by fatigue detection.

Exposes a FastAPI endpoint that, upon receiving a trigger, executes one
episode of the ACT imitation-learning policy to pick up and deliver a
candy basket.

Usage:
    uvicorn robot.arm_server:app --host 0.0.0.0 --port 8766

Requires:
    - LeRobot (lerobot) installed with ACT policy support
    - SO-ARM101 leader/follower connected via USB
    - Trained ACT checkpoint at the path specified in config
"""

import logging
import subprocess
import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from robot.config import (
    ACT_CHECKPOINT_PATH,
    CONTROL_FPS,
    ROBOT_TYPE,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="SO-ARM101 Candy Delivery", version="1.0.0")

# Global lock to prevent concurrent arm operations
_arm_lock = threading.Lock()
_arm_running = False


class TriggerRequest(BaseModel):
    fatigue_score: float = 0.0


class TriggerResponse(BaseModel):
    status: str
    message: str
    duration_seconds: float = 0.0


@app.get("/health")
def health():
    return {"status": "ok", "arm_running": _arm_running}


@app.post("/trigger", response_model=TriggerResponse)
def trigger_candy_delivery(req: TriggerRequest):
    """Trigger one episode of ACT candy basket delivery.

    Returns immediately if the arm is already running (mode: single).
    """
    global _arm_running

    if _arm_running:
        raise HTTPException(
            status_code=409,
            detail="Arm is already executing a delivery. Please wait.",
        )

    checkpoint = Path(ACT_CHECKPOINT_PATH)
    if not checkpoint.exists():
        raise HTTPException(
            status_code=500,
            detail=f"ACT checkpoint not found: {checkpoint}",
        )

    logger.info(
        "Candy delivery triggered (fatigue_score=%.2f)", req.fatigue_score
    )

    _arm_running = True
    start = time.time()

    try:
        result = subprocess.run(
            [
                "python",
                "-m",
                "lerobot.scripts.control_robot",
                f"--robot.type={ROBOT_TYPE}",
                "--control.type=record",
                f"--control.fps={CONTROL_FPS}",
                f"--control.policy.path={ACT_CHECKPOINT_PATH}",
                "--control.display_data=false",
                "--control.num_episodes=1",
                "--control.warmup_time_s=2",
                "--control.reset_time_s=5",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        duration = time.time() - start

        if result.returncode != 0:
            logger.error("LeRobot stderr: %s", result.stderr[:500])
            return TriggerResponse(
                status="error",
                message=f"LeRobot exited with code {result.returncode}",
                duration_seconds=duration,
            )

        logger.info("Candy delivery completed in %.1fs", duration)
        return TriggerResponse(
            status="completed",
            message="Candy basket delivered successfully!",
            duration_seconds=duration,
        )

    except subprocess.TimeoutExpired:
        logger.error("LeRobot timed out after 120s")
        return TriggerResponse(
            status="timeout",
            message="Arm operation timed out",
            duration_seconds=time.time() - start,
        )
    except Exception as e:
        logger.exception("Unexpected error during arm operation")
        return TriggerResponse(
            status="error",
            message=str(e),
            duration_seconds=time.time() - start,
        )
    finally:
        _arm_running = False
