---
license: mit
language:
  - ja
  - en
tags:
  - tabular-data
  - cfd-simulation
  - openfoam
  - airflow
  - physics-ml
task_categories:
  - tabular-regression
size_categories:
  - n<1K
---

# KandenAiHackathonAirflow — 室内気流CFDシミュレーションデータセット

> **English Summary**
> A tabular dataset of 54 CFD (Computational Fluid Dynamics) simulation cases for a 6m × 5m × 2.7m office room. Generated with OpenFOAM's buoyantSimpleFoam solver, the dataset systematically varies air conditioning speed, AC temperature, window state, and ventilation rate to capture indoor airflow, temperature, and CO2 distribution. Designed for training physics-informed neural network (PINN) surrogate models with NVIDIA Physics-NeMo.

---

## データセット概要

本データセットは、**空間AIブレイン** プロジェクトにおける気流AIシミュレーションの学習データです。

オフィス室内の空調・換気・窓の開閉条件を系統的に変化させ、OpenFOAM（buoyantSimpleFoam）で定常CFDシミュレーションを実行した結果の入力パラメータを記録しています。このデータを基に、NVIDIA Physics-NeMo でサロゲートモデルを学習し、高コストなCFD計算を高速なニューラルネット推論で代替します。

---

## データの内容

| 項目 | 詳細 |
|------|------|
| **ケース数** | 54 |
| **フォーマット** | CSV (Parquet自動変換済み) |
| **データ分割** | train: 54行 |
| **サイズ** | 約2 kB |

### カラム説明

| カラム名 | 型 | 値域 | 説明 |
|---------|-----|------|------|
| `case_id` | string | `case_0000` 〜 `case_0053` | シミュレーションケースの一意識別子 |
| `n_cells` | int | 50,160 (固定) | CFDメッシュのセル数 |
| `ac_speed` | float | 1.0 / 3.0 / 5.0 | エアコン吹き出し風速 (m/s) |
| `ac_temperature` | float | 20.0 / 24.0 / 28.0 | エアコン設定温度 (°C) |
| `window_open` | bool | True / False | 窓の開閉状態 |
| `layout_id` | int | 0 (固定) | 家具レイアウトID |
| `ventilation_rate` | float | 0.0 / 0.05 / 0.1 | 換気ファン流量 (m³/s) |

### パラメータグリッド

全組み合わせの直積: 3 × 3 × 2 × 3 × 1 = **54ケース**

| パラメータ | 値 |
|-----------|-----|
| AC風速 (m/s) | 1.0, 3.0, 5.0 |
| AC温度 (°C) | 20.0, 24.0, 28.0 |
| 窓開閉 | 開 (True), 閉 (False) |
| 換気量 (m³/s) | 0.0, 0.05, 0.1 |
| レイアウトID | 0 |

---

## シミュレーション環境

### 部屋構成

| 項目 | 詳細 |
|------|------|
| 部屋サイズ | 6.0m (x) × 5.0m (y) × 2.7m (z) |
| エアコン (吹出口) | x=0, y中央, 高さ2.4m — 室内方向 & やや下向きに送風 |
| 換気ファン (排気口) | x=6.0, y中央, 高さ2.4m |
| 窓 | y=5.0壁面, 幅1.2m × 高さ1.0m |
| デスク | 4台 (2×2グリッド配置) |
| 在席者 | 4名 (発熱75W/人, CO2排出0.005 L/s/人) |
| 外気温 | 30.0°C |

### CFDソルバー

| 項目 | 詳細 |
|------|------|
| ソルバー | OpenFOAM `buoyantSimpleFoam` |
| 解析タイプ | 定常 (Steady-state) |
| 物理モデル | 浮力考慮 (温度・CO2による密度変化) |
| 出力フィールド | 速度 (u, v, w), 圧力 (p), 温度 (T), CO2濃度 |

---

## 使用方法

### Python (datasets ライブラリ)

```python
from datasets import load_dataset

dataset = load_dataset("SeiyaCM/KandenAiHackathonAirflow")
df = dataset["train"].to_pandas()
print(df.head())
print(f"Total cases: {len(df)}")
```

### pandas

```python
import pandas as pd

df = pd.read_csv("hf://datasets/SeiyaCM/KandenAiHackathonAirflow/data.csv")
print(df.describe())
```

---

## 想定ユースケース

- Physics-NeMo サロゲートモデルの学習データ
- 室内環境制御アルゴリズムの開発・評価
- CFDシミュレーションのパラメータスタディ
- 物理情報ニューラルネットワーク (PINN) の研究

---

## 注意点・制約・バイアス / Limitations & Bias

- **ケース数が限定的**: 54ケースのみであり、パラメータ空間の細かい補間には注意が必要です
- **単一レイアウト**: layout_id=0（2×2グリッド配置）のみ。他のレイアウトは含まれていません
- **定常解析のみ**: 時間変化を伴う非定常現象（人の出入り、急激な温度変化等）は考慮されていません
- **固定メッシュ解像度**: 全ケースで50,160セルの同一メッシュを使用
- **理想化された条件**: 家具の熱容量、壁面の断熱性能等は簡略化されています
- **外気温固定**: 外気温は30.0°Cで固定されており、季節変動は未考慮です

---

## ライセンス / License

MIT License

---

## 関連リンク / Related Links

- **GitHub**: [SeiyaCM/kanden-ai-hackathon](https://github.com/SeiyaCM/kanden-ai-hackathon)
- **気流モデル**: [SeiyaCM/KandenAiHackathonAirflowModel](https://huggingface.co/SeiyaCM/KandenAiHackathonAirflowModel)
- **姿勢データセット**: [SeiyaCM/KandenAiHackathonPosture2](https://huggingface.co/datasets/SeiyaCM/KandenAiHackathonPosture2)
