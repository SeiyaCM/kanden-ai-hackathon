---
license: apache-2.0
language:
  - ja
  - en
tags:
  - physics-informed-neural-network
  - onnx
  - airflow-simulation
  - cfd-surrogate
  - indoor-environment
datasets:
  - SeiyaCM/KandenAiHackathonAirflow
pipeline_tag: tabular-regression
---

# Airflow Surrogate — 室内気流サロゲートモデル

> **English Summary**
> A physics-informed neural network (PINN) surrogate model that predicts indoor airflow fields (velocity, pressure, temperature, CO2) given spatial coordinates and room conditions. Trained on 54 CFD cases generated with OpenFOAM buoyantSimpleFoam, incorporating Navier-Stokes residuals as a physics loss term. The model replaces costly CFD simulations with millisecond-scale ONNX inference for real-time workspace environment control on DGX Spark.

---

## モデル概要

本モデルは、**空間AIブレイン** プロジェクトの一部として開発された、オフィス室内の気流・温度・CO2分布をリアルタイムに予測する物理情報ニューラルネットワーク（PINNs）サロゲートモデルです。

従来のCFD（数値流体力学）シミュレーションには数分〜数時間の計算時間が必要ですが、本モデルはこれをミリ秒単位のニューラルネット推論に置き換え、空調制御の意思決定にリアルタイムで活用できます。

---

## ベースモデル / Base Model

- **アーキテクチャ**: 全結合ネットワーク (MLP) — 8 → 256 → 256 → 256 → 256 → 256 → 256 → 6
- **活性化関数**: SiLU (Sigmoid Linear Unit)
- **フレームワーク**: PyTorch + NVIDIA Physics-NeMo の物理損失設計を参考

---

## 学習方法 / Training

- **手法**: 教師あり学習 + 物理情報損失（Physics-Informed Loss）
  - **データ損失**: CFDシミュレーション結果との MSE
  - **物理損失**: Navier-Stokes 方程式（連続の式 + 運動量方程式）の残差を自動微分で計算
  - **総損失**: `L = L_data + 0.1 × L_physics`
- **GPU環境**: NVIDIA RTX A5000（CUDA）
- **オプティマイザ**: Adam (lr=1e-3)
- **スケジューラ**: CosineAnnealingLR (T_max=1000, eta_min=1e-6)
- **エポック数**: 1,000
- **バッチサイズ**: 4,096
- **データ分割**: train / val / test（CFD 54ケースを空間点レベルで分割）

---

## 使用データ / Training Data

- **データセット**: [SeiyaCM/KandenAiHackathonAirflow](https://huggingface.co/datasets/SeiyaCM/KandenAiHackathonAirflow)
- **ケース数**: 54ケースのCFDシミュレーション結果
- **生成方法**: OpenFOAM `buoyantSimpleFoam` による定常CFD解析
- **パラメータ**: AC風速 (1.0/3.0/5.0 m/s) × AC温度 (20/24/28 °C) × 窓開閉 × 換気量 (0.0/0.05/0.1 m³/s)
- **部屋**: 6.0m × 5.0m × 2.7m のオフィス、4名在席

---

## 性能・評価指標 / Performance

評価指標: RMSE, MAE, Relative L2 Error, Max Error（各フィールドごと）

| 指標 | 説明 |
|------|------|
| RMSE | 二乗平均平方根誤差（MinMax正規化空間 [0,1] 上） |
| Relative L2 | CFD真値に対する相対 L2 誤差 |
| MAE | 平均絶対誤差 |

> **注**: 具体的な数値はバリデーション実行環境に依存します。`validate_model.py` で再現可能です。

---

## 入出力仕様 / Input & Output

### 入力 (Input)

| 名前 | 形状 | 型 | 説明 |
|------|------|-----|------|
| `input` | `(batch, 8)` | float32 | MinMax正規化済みの空間座標 + 環境パラメータ |

**入力チャネル（正規化前の物理量）**:

| Index | パラメータ | 値域 | 正規化方法 |
|-------|-----------|------|-----------|
| 0 | x（空間座標） | 0.0 〜 6.0 m | MinMax |
| 1 | y（空間座標） | 0.0 〜 5.0 m | MinMax |
| 2 | z（空間座標） | 0.0 〜 2.7 m | MinMax |
| 3 | ac_speed（AC風速） | 1.0 〜 5.0 m/s | MinMax |
| 4 | ac_temp（AC温度） | 20.0 〜 28.0 °C | MinMax |
| 5 | window_open（窓開閉） | 0 or 1 | そのまま |
| 6 | layout_id（レイアウト） | 0 〜 2 | / 2.0 |
| 7 | vent_rate（換気量） | 0.0 〜 0.1 m³/s | MinMax |

### 出力 (Output)

| 名前 | 形状 | 型 | 説明 |
|------|------|-----|------|
| `u` | `(batch, 6)` | float32 | MinMax正規化 [0,1] された流体場の予測値 |

**出力チャネル**:

| Index | フィールド | 説明 |
|-------|-----------|------|
| 0 | u | x方向速度成分 |
| 1 | v | y方向速度成分 |
| 2 | w | z方向速度成分 |
| 3 | p | 圧力 |
| 4 | T | 温度 |
| 5 | CO2 | CO2濃度 |

---

## 推論方法 / Inference

### ONNX Runtime (Python)

```python
import numpy as np
import onnxruntime as ort

# モデルのロード
session = ort.InferenceSession("airflow_surrogate.onnx")

FIELD_NAMES = ["u", "v", "w", "p", "T", "CO2"]

# 正規化パラメータ
NORM = {
    "coords_min": [0.0, 0.0, 0.0],
    "coords_max": [6.0, 5.0, 2.7],
    "ac_speed_min": 1.0, "ac_speed_max": 5.0,
    "ac_temp_min": 20.0, "ac_temp_max": 28.0,
    "vent_rate_min": 0.0, "vent_rate_max": 0.1,
}

def minmax(val, vmin, vmax):
    return (val - vmin) / (vmax - vmin) if vmax != vmin else 0.0

# 入力: デスク位置 (1.5, 0.9, 1.2), AC風速3m/s, AC温度24°C, 窓閉, レイアウト0, 換気0.05
input_array = np.array([[
    minmax(1.5, 0.0, 6.0),   # x
    minmax(0.9, 0.0, 5.0),   # y
    minmax(1.2, 0.0, 2.7),   # z
    minmax(3.0, 1.0, 5.0),   # ac_speed
    minmax(24.0, 20.0, 28.0), # ac_temp
    0.0,                       # window_open (閉)
    0.0,                       # layout_id / 2.0
    minmax(0.05, 0.0, 0.1),  # vent_rate
]], dtype=np.float32)

# 推論
result = session.run(["u"], {"input": input_array})[0]

# 結果表示 (MinMax正規化 [0,1] 空間)
for name, val in zip(FIELD_NAMES, result[0]):
    print(f"{name}: {val:.4f}")
```

---

## 想定ユースケース / Intended Use

- リアルタイム室内環境モニタリング（温度・CO2・気流の予測）
- スマートホーム連携による空調の最適制御
- 空気淀み（CO2滞留）の検知と換気判断
- CFDシミュレーションの高速代替（パラメータスタディ）

## 非推奨ユースケース / Out-of-Scope Use

- 安全性が重要な空調・換気設計の最終判断
- 学習パラメータ範囲外の条件での予測（AC風速 > 5 m/s、AC温度 < 20°C 等）
- 非定常現象（人の出入り、急激な温度変化）の予測
- 本モデルが学習していないレイアウト（layout_id ≠ 0）での精密な予測
- 建築基準法等の法的要件を満たすための根拠としての利用

---

## 制約・限界・バイアス / Limitations & Bias

- **学習データが54ケースのみ**: パラメータグリッドの離散点でのみ学習しており、補間精度には限界があります
- **単一レイアウト**: layout_id=0（2×2グリッド配置）のデータのみで学習。他のレイアウトでの予測精度は未検証です
- **定常解析のみ**: 時間変化を伴う非定常現象（ドア開閉、人の移動等）は考慮されていません
- **固定メッシュ解像度**: 全ケースで50,160セルの同一メッシュを使用しており、メッシュ依存性は未検証です
- **理想化された条件**: 家具の熱容量、壁面の断熱性能、外気温変動等は簡略化されています
- **外気温固定**: 外気温30.0°Cで固定。季節変動や昼夜の温度変化は未考慮です
- **物理損失の近似**: 粘性項（ラプラシアン）を省略した簡易版Navier-Stokes残差を使用しています

---

## ライセンス / License

Apache License 2.0

---

## 引用 / Citation

```bibtex
@misc{kanden_airflow_model_2025,
  title   = {Airflow Surrogate: Physics-Informed Neural Network for Indoor CFD Prediction},
  author  = {Team NANIWA-Factory},
  year    = {2025},
  url     = {https://huggingface.co/SeiyaCM/KandenAiHackathonAirflowModel},
  note    = {Kanden AI Hackathon — Space AI Brain Project}
}
```

---

## 関連リンク / Related Links

- **GitHub**: [SeiyaCM/kanden-ai-hackathon](https://github.com/SeiyaCM/kanden-ai-hackathon)
- **HuggingFace モデル**: [SeiyaCM/KandenAiHackathonAirflowModel](https://huggingface.co/SeiyaCM/KandenAiHackathonAirflowModel)
- **学習データ**: [SeiyaCM/KandenAiHackathonAirflow](https://huggingface.co/datasets/SeiyaCM/KandenAiHackathonAirflow)
- **姿勢分類モデル**: [SeiyaCM/KandenAiHackathonPostureModel](https://huggingface.co/SeiyaCM/KandenAiHackathonPostureModel)
