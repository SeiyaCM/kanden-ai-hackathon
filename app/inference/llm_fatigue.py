"""LLM-based fatigue scoring via Ollama (local LLM on DGX Spark).

Implements an "agent loop" pattern: maintains a sliding window of recent
observations and feeds temporal context to the LLM for richer fatigue
assessment than instantaneous rule-based scoring.

Falls back to the existing rule-based FatigueScorer when Ollama is
unavailable or times out.
"""

import json
import logging
import time
from collections import deque
from datetime import datetime, timezone

import requests

from app.inference.fatigue import FatigueScorer

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
あなたはオフィスワーカーの疲労度を評価するAIです。
複数のセンサーから得られたデータの時系列を分析し、総合的な疲労スコアを出力してください。

## 評価基準
- 姿勢が悪化傾向にある場合、疲労が蓄積していると判断
- ネガティブな発言は疲労の強いシグナル
- 環境ストレス（CO2上昇・気温偏差・換気不良）は疲労を助長する
- 複数要因が同時に悪化している場合はシナジー効果で高めに評価

## 出力形式
以下のJSON形式のみで回答してください。他のテキストは含めないでください。
{"fatigue_score": 0.0, "reasoning": "判断理由を1文で"}

fatigue_score は 0.0（元気）〜 1.0（極度の疲労）の範囲です。\
"""

_POSTURE_LABELS = {
    "good": "良好",
    "slouch": "猫背",
    "chin_rest": "頬杖",
    "stretch": "ストレッチ",
}


class LLMFatigueScorer:
    """Agent-loop fatigue scorer backed by a local Ollama LLM.

    Maintains a sliding window of recent observations and constructs a
    temporal-context prompt for the LLM.  On failure, transparently falls
    back to the rule-based ``FatigueScorer``.
    """

    def __init__(
        self,
        ollama_host: str = "http://localhost:11434",
        model_name: str = "qwen3:8b",
        timeout: float = 3.0,
        window_size: int = 5,
    ) -> None:
        self._host = ollama_host.rstrip("/")
        self._model = model_name
        self._timeout = timeout
        self._observations: deque[dict] = deque(maxlen=window_size)
        self._fallback = FatigueScorer()
        self._available: bool | None = None

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------
    def is_available(self) -> bool:
        """Check Ollama connectivity (cached after first call)."""
        if self._available is None:
            try:
                r = requests.get(f"{self._host}/api/tags", timeout=2.0)
                self._available = r.status_code == 200
            except Exception:
                self._available = False
            logger.info("Ollama available: %s", self._available)
        return self._available

    def reset_availability(self) -> None:
        """Force re-check on next call (e.g. after Ollama restart)."""
        self._available = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def score(
        self,
        posture_result: dict,
        airflow_result: dict,
        voice_result: dict | None = None,
    ) -> dict:
        """Compute fatigue score via LLM with rule-based fallback.

        Returns a dict compatible with ``FatigueScorer.compute()`` output,
        augmented with ``llm_used``, ``llm_status``, and ``llm_reasoning``
        keys.
        """
        self._add_observation(posture_result, airflow_result, voice_result)

        # Always compute rule-based as baseline / fallback
        rule_result = self._fallback.compute(
            posture_result, airflow_result, voice_result
        )

        if not self.is_available():
            return {**rule_result, "llm_used": False, "llm_status": "unavailable"}

        prompt = self._build_prompt(posture_result, airflow_result, voice_result)
        llm_response = self._call_ollama(prompt)

        if llm_response is None:
            return {**rule_result, "llm_used": False, "llm_status": "timeout"}

        return {
            **rule_result,
            "fatigue_score": llm_response["fatigue_score"],
            "llm_used": True,
            "llm_status": "ok",
            "llm_reasoning": llm_response.get("reasoning", ""),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _add_observation(
        self,
        posture_result: dict,
        airflow_result: dict,
        voice_result: dict | None,
    ) -> None:
        self._observations.append(
            {
                "time": time.time(),
                "posture_class": posture_result["class"],
                "posture_confidence": posture_result["confidence"],
                "posture_score": self._fallback.compute_posture_score(posture_result),
                "env_score": self._fallback.compute_environment_score(airflow_result),
                "voice_score": voice_result["voice_score"] if voice_result else 0.0,
                "voice_transcript": (
                    voice_result.get("transcript", "") if voice_result else ""
                ),
                "voice_keywords": (
                    voice_result.get("matched_keywords", []) if voice_result else []
                ),
            }
        )

    def _build_prompt(
        self,
        posture_result: dict,
        airflow_result: dict,
        voice_result: dict | None,
    ) -> str:
        now = time.time()
        lines: list[str] = []

        # Observation history
        if len(self._observations) > 1:
            lines.append("## 直近の観測履歴")
            for i, obs in enumerate(self._observations):
                elapsed = int(now - obs["time"])
                posture_ja = _POSTURE_LABELS.get(
                    obs["posture_class"], obs["posture_class"]
                )
                voice_info = "なし"
                if obs["voice_score"] > 0.1:
                    kw = ", ".join(obs["voice_keywords"]) if obs["voice_keywords"] else ""
                    voice_info = f"スコア{obs['voice_score']:.1f}"
                    if kw:
                        voice_info += f' ("{kw}")'
                lines.append(
                    f"[{i + 1}] {elapsed}秒前 | "
                    f"姿勢: {posture_ja}({obs['posture_confidence']:.2f}) | "
                    f"音声: {voice_info} | "
                    f"環境ストレス: {obs['env_score']:.2f}"
                )
            lines.append("")

        # Current state
        current = self._observations[-1]
        posture_ja = _POSTURE_LABELS.get(
            current["posture_class"], current["posture_class"]
        )
        lines.append("## 現在の状態")
        lines.append(
            f"姿勢: {posture_ja} (信頼度{current['posture_confidence']:.2f}, "
            f"姿勢スコア{current['posture_score']:.2f})"
        )

        voice_desc = "なし"
        if voice_result and voice_result["voice_score"] > 0.1:
            voice_desc = f"スコア{voice_result['voice_score']:.1f}"
            if voice_result.get("matched_keywords"):
                voice_desc += f" (検出: {', '.join(voice_result['matched_keywords'])})"
            if voice_result.get("transcript"):
                voice_desc += f' / 発話内容: "{voice_result["transcript"]}"'
        lines.append(f"音声: {voice_desc}")
        lines.append(f"環境ストレス: {current['env_score']:.2f}")

        return "\n".join(lines)

    def _call_ollama(self, prompt: str) -> dict | None:
        """POST to Ollama /api/generate and parse JSON response."""
        try:
            r = requests.post(
                f"{self._host}/api/generate",
                json={
                    "model": self._model,
                    "system": _SYSTEM_PROMPT,
                    "prompt": prompt,
                    "format": "json",
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 150,
                    },
                },
                timeout=self._timeout,
            )
            r.raise_for_status()
            raw = r.json().get("response", "")
            return self._parse_response(raw)
        except requests.Timeout:
            logger.warning("Ollama request timed out (%.1fs)", self._timeout)
            return None
        except Exception:
            logger.exception("Ollama request failed")
            return None

    @staticmethod
    def _parse_response(raw: str) -> dict | None:
        """Extract fatigue_score from LLM JSON output."""
        try:
            data = json.loads(raw)
            score = float(data["fatigue_score"])
            score = max(0.0, min(1.0, score))
            return {
                "fatigue_score": score,
                "reasoning": data.get("reasoning", ""),
            }
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            logger.warning("Failed to parse LLM response: %s", raw[:200])
            return None
