"""Headless smoke test — verify both ONNX models load and produce valid output.

Usage:
    python -m app.test_inference
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path so "app" package is importable
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import numpy as np

from app.inference.posture import PostureInference
from app.inference.airflow import AirflowInference
from app.inference.fatigue import FatigueScorer


def test_posture():
    print("[1/3] Posture model ...")
    model = PostureInference()
    print(f"  providers={model.session.get_providers()}")
    # Dummy BGR frame (224x224)
    dummy_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    result = model.predict(dummy_frame)

    assert result["class"] in ("good", "slouch", "chin_rest", "stretch"), (
        f"Unexpected class: {result['class']}"
    )
    assert 0.0 <= result["confidence"] <= 1.0
    assert len(result["probabilities"]) == 4
    print(f"  class={result['class']}  confidence={result['confidence']:.3f}")
    print(f"  probabilities={result['probabilities']}")
    print("  OK")
    return result


def test_airflow():
    print("[2/3] Airflow model ...")
    model = AirflowInference()
    print(f"  providers={model.session.get_providers()}")
    # Center of room, moderate AC settings
    result = model.predict_at_point(
        x=3.0, y=2.5, z=1.2,
        ac_speed=3.0, ac_temp=24.0,
        window_open=0, layout_id=0, vent_rate=0.05,
    )

    expected_keys = {"u", "v", "w", "p", "T", "CO2"}
    assert set(result.keys()) == expected_keys, f"Unexpected keys: {result.keys()}"
    for k, v in result.items():
        assert isinstance(v, float), f"{k} is not float"
        print(f"  {k} = {v:.4f}")
    print("  OK")
    return result


def test_fatigue(posture_result, airflow_result):
    print("[3/3] Fatigue scorer ...")
    scorer = FatigueScorer()
    result = scorer.compute(posture_result, airflow_result)

    assert 0.0 <= result["fatigue_score"] <= 1.0
    assert "timestamp" in result
    assert "synergy_score" in result
    print(f"  fatigue_score = {result['fatigue_score']:.3f}")
    print(f"  synergy_score = {result['synergy_score']:.3f}")
    print(f"  posture_score = {result['posture_score']:.3f}")
    print(f"  environment_score = {result['environment_score']:.3f}")
    print("  OK")


def test_synergy():
    """Unit test for synergy logic — no ONNX models needed."""
    print("[4/4] Synergy logic ...")
    scorer = FatigueScorer()

    def _make_posture(cls, conf=1.0):
        return {"class": cls, "confidence": conf, "probabilities": [0.25] * 4}

    def _make_airflow(env_score_target):
        # Craft airflow so compute_environment_score ≈ env_score_target.
        # stagnation_stress dominates at 40%; set speed=0 → stagnation=1.0,
        # co2 and temp to hit the target.
        # env = 0.4*stag + 0.4*co2 + 0.2*temp
        # We set stag=target, co2=target, temp=target for simplicity by
        # directly using known inverse formulas.
        # Easier: just mock via monkeypatch-style by computing directly.
        # Actually, let's use a simpler approach: override compute_environment_score.
        pass

    # Instead of crafting exact airflow dicts, we test the synergy math
    # by calling compute with known posture/env/voice scores.
    # We'll subclass to inject known scores.
    class _MockScorer(FatigueScorer):
        def __init__(self, p, e):
            self._p = p
            self._e = e

        def compute_posture_score(self, posture_result):
            return self._p

        def compute_environment_score(self, airflow_result):
            return self._e

    dummy_posture = {"class": "good", "confidence": 1.0, "probabilities": [1, 0, 0, 0]}
    dummy_airflow = {"u": 0, "v": 0, "w": 0, "p": 0, "T": 0.5, "CO2": 0}

    # α=0.15, β=0.20
    scenarios = [
        # (P, E, V_or_None, expected_min, expected_max, label)
        (0.0, 0.1, 0.0, 0.01, 0.03, "全部良好"),
        (0.8, 0.1, 0.1, 0.45, 0.49, "姿勢だけ悪い"),
        (0.8, 0.8, 0.1, 0.69, 0.73, "姿勢+環境悪い"),
        (0.8, 0.8, 0.8, 1.0, 1.0, "全部悪い (clamp)"),
        (0.8, 0.8, None, 0.87, 0.89, "2モダリティ"),
    ]

    for p, e, v, lo, hi, label in scenarios:
        s = _MockScorer(p, e)
        voice = {"voice_score": v} if v is not None else None
        result = s.compute(dummy_posture, dummy_airflow, voice)
        score = result["fatigue_score"]
        synergy = result["synergy_score"]
        ok = lo <= score <= hi
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {label}: P={p} E={e} V={v} → "
              f"fatigue={score:.3f} synergy={synergy:.3f} (expected {lo}-{hi})")
        assert ok, f"{label}: {score:.3f} not in [{lo}, {hi}]"

    print("  OK")


def main():
    print("=" * 50)
    print("空間AIブレイン - 推論スモークテスト")
    print("=" * 50)
    try:
        posture_result = test_posture()
        airflow_result = test_airflow()
        test_fatigue(posture_result, airflow_result)
        test_synergy()
        print("\nAll tests passed!")
    except Exception as e:
        print(f"\nFAILED: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
