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
    print(f"  fatigue_score = {result['fatigue_score']:.3f}")
    print(f"  posture_score = {result['posture_score']:.3f}")
    print(f"  environment_score = {result['environment_score']:.3f}")
    print("  OK")


def main():
    print("=" * 50)
    print("空間AIブレイン - 推論スモークテスト")
    print("=" * 50)
    try:
        posture_result = test_posture()
        airflow_result = test_airflow()
        test_fatigue(posture_result, airflow_result)
        print("\nAll tests passed!")
    except Exception as e:
        print(f"\nFAILED: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
