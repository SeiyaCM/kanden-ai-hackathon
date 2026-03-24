"""Combined fatigue scoring from posture + airflow AI outputs.

Produces a fatigue_score in [0, 1] that maps to the FatiguePayload schema
defined in docs/openapi.yml.
"""

import math
from datetime import datetime, timezone


# Posture → fatigue base scores
POSTURE_FATIGUE_MAP = {
    "good": 0.0,
    "slouch": 0.7,
    "chin_rest": 0.9,
    "stretch": 0.3,
}

POSTURE_WEIGHT = 0.5
ENVIRONMENT_WEIGHT = 0.2
VOICE_WEIGHT = 0.3

# Fallback weights when voice modality is unavailable
_POSTURE_WEIGHT_NO_VOICE = 0.7
_ENVIRONMENT_WEIGHT_NO_VOICE = 0.3


class FatigueScorer:
    """Merge posture detection and airflow environment into a single score."""

    @staticmethod
    def compute_posture_score(posture_result: dict) -> float:
        """Map posture class → fatigue, weighted by model confidence."""
        base = POSTURE_FATIGUE_MAP.get(posture_result["class"], 0.5)
        return base * posture_result["confidence"]

    @staticmethod
    def compute_environment_score(airflow_result: dict) -> float:
        """Derive environmental stress from normalized airflow outputs.

        All airflow values are in [0, 1] (MinMax-normalized).
        """
        # Air stagnation: low speed → poor circulation → stress ↑
        speed = math.sqrt(
            airflow_result["u"] ** 2
            + airflow_result["v"] ** 2
            + airflow_result["w"] ** 2
        )
        stagnation_stress = max(0.0, 1.0 - speed * 3.0)

        # CO2: higher normalized value → worse air quality
        co2_stress = min(1.0, max(0.0, airflow_result["CO2"] * 2.0 - 0.5))

        # Temperature comfort: 0.5 ≈ comfort zone (~24 °C), deviation = stress
        temp_stress = min(1.0, abs(airflow_result["T"] - 0.5) * 3.0)

        return 0.4 * stagnation_stress + 0.4 * co2_stress + 0.2 * temp_stress

    def compute(
        self,
        posture_result: dict,
        airflow_result: dict,
        voice_result: dict | None = None,
    ) -> dict:
        """Return combined fatigue assessment.

        Returns dict matching docs/openapi.yml FatiguePayload schema.
        When *voice_result* is ``None`` the original 2-modality weights are
        used for backward compatibility.
        """
        posture_score = self.compute_posture_score(posture_result)
        env_score = self.compute_environment_score(airflow_result)

        if voice_result is not None:
            voice_score = voice_result["voice_score"]
            fatigue_score = (
                POSTURE_WEIGHT * posture_score
                + ENVIRONMENT_WEIGHT * env_score
                + VOICE_WEIGHT * voice_score
            )
        else:
            voice_score = 0.0
            fatigue_score = (
                _POSTURE_WEIGHT_NO_VOICE * posture_score
                + _ENVIRONMENT_WEIGHT_NO_VOICE * env_score
            )

        fatigue_score = max(0.0, min(1.0, fatigue_score))

        return {
            "fatigue_score": fatigue_score,
            "posture_score": posture_score,
            "environment_score": env_score,
            "voice_score": voice_score,
            "posture_detail": posture_result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
