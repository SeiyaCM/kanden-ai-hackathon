"""Real-time speech analysis using faster-whisper for negative utterance detection.

Captures audio from the system microphone in a background thread, periodically
transcribes via faster-whisper, and checks for negative keywords that indicate
mental fatigue or stress.
"""

import threading
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

from app.config import (
    AUDIO_BUFFER_SECONDS,
    AUDIO_SAMPLE_RATE,
    NEGATIVE_KEYWORDS,
    VOICE_SCORE_DECAY,
    WHISPER_COMPUTE_TYPE,
    WHISPER_DEVICE,
    WHISPER_MODEL_SIZE,
)


class AudioSpeechAnalyzer:
    """Background audio capture + faster-whisper transcription + keyword scoring."""

    def __init__(self) -> None:
        self._model = WhisperModel(
            WHISPER_MODEL_SIZE,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE_TYPE,
        )

        self._sample_rate = AUDIO_SAMPLE_RATE
        self._buffer_size = AUDIO_SAMPLE_RATE * AUDIO_BUFFER_SECONDS
        self._buffer = np.zeros(self._buffer_size, dtype=np.float32)
        self._buffer_lock = threading.Lock()

        self._voice_score = 0.0
        self._running = True

        self._stream = sd.InputStream(
            samplerate=self._sample_rate,
            channels=1,
            dtype="float32",
            blocksize=1024,
            callback=self._audio_callback,
        )
        self._stream.start()

    # ------------------------------------------------------------------
    # Audio capture
    # ------------------------------------------------------------------
    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:  # noqa: ANN001
        """sounddevice callback — append incoming audio to rolling buffer."""
        mono = indata[:, 0]
        with self._buffer_lock:
            shift = len(mono)
            self._buffer = np.roll(self._buffer, -shift)
            self._buffer[-shift:] = mono

    # ------------------------------------------------------------------
    # Transcription + keyword matching
    # ------------------------------------------------------------------
    def _transcribe(self) -> str:
        with self._buffer_lock:
            audio = self._buffer.copy()

        segments, _ = self._model.transcribe(audio, language="ja", beam_size=1)
        return "".join(seg.text for seg in segments)

    @staticmethod
    def _match_keywords(text: str) -> tuple[bool, list[str], float]:
        """Check *text* against the negative keyword dictionary.

        Returns (detected, matched_keywords, max_severity).
        """
        matched: list[str] = []
        max_severity = 0.0
        for keyword, severity in NEGATIVE_KEYWORDS.items():
            if keyword in text:
                matched.append(keyword)
                max_severity = max(max_severity, severity)
        return bool(matched), matched, max_severity

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def analyze(self) -> dict:
        """Transcribe the current audio buffer and compute voice fatigue score.

        Call this periodically from the main loop (every AUDIO_ANALYZE_INTERVAL
        seconds).  Returns a dict with voice_score, transcript, and keyword info.
        """
        transcript = self._transcribe()
        detected, matched, severity = self._match_keywords(transcript)

        if detected:
            self._voice_score = severity
        else:
            self._voice_score *= VOICE_SCORE_DECAY

        return {
            "voice_score": self._voice_score,
            "transcript": transcript,
            "negative_detected": detected,
            "matched_keywords": matched,
        }

    def stop(self) -> None:
        """Cleanly shut down the audio stream."""
        self._running = False
        if self._stream.active:
            self._stream.stop()
        self._stream.close()
