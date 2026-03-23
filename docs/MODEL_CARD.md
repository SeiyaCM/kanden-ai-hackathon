---
license: apache-2.0
language:
  - ja
  - en
tags:
  - image-classification
  - onnx
  - resnet
  - posture-detection
  - fatigue-detection
datasets:
  - SeiyaCM/KandenAiHackathonPosture2
pipeline_tag: image-classification
---

# Posture Classifier — エンジニア姿勢分類モデル

> **English Summary**
> A ResNet18-based posture classifier that detects four sitting postures of engineers (good, slouch, chin rest, stretch) for real-time fatigue monitoring. Trained on 52,500 synthetic images generated with Stable Diffusion + ControlNet, achieving **97.33 % validation accuracy** with zero false positives on slouch detection. Exported as a lightweight ONNX model (~42 MB) for edge deployment on DGX Spark.

---

## モデル概要

本モデルは、**空間AIブレイン** プロジェクトの一部として開発された、エンジニアの座り姿勢をリアルタイムに分類する画像分類モデルです。Webカメラ映像から以下の4つの姿勢を検出し、疲労度のスコアリングに活用されます。

| クラスID | クラス名 | 説明 | 疲労マッピング |
|----------|---------|------|--------------|
| 0 | `good` | 正しい姿勢で作業中 | 0.0（疲労なし） |
| 1 | `slouch` | 猫背で前傾した疲労姿勢 | 0.7（高疲労） |
| 2 | `chin_rest` | 頬杖をつく（ストレス・集中力低下） | 0.9（非常に高疲労） |
| 3 | `stretch` | ストレッチ・伸び（休憩・回復行動） | 0.3（軽度） |

---

## ベースモデル / Base Model

- **アーキテクチャ**: ResNet18 (`torchvision.models.resnet18`)
- **事前学習**: ImageNet (ResNet18_Weights.DEFAULT)
- **変更箇所**: 最終全結合層を `nn.Linear(512, 4)` に置換

---

## 学習方法 / Training

- **手法**: Full fine-tuning（全レイヤーを再学習）
- **GPU環境**: NVIDIA RTX A5000 × 4 (DataParallel)
- **オプティマイザ**: AdamW (lr=5e-4, weight_decay=1e-4)
- **スケジューラ**: CosineAnnealingLR (T_max=30, eta_min=1e-6)
- **損失関数**: CrossEntropyLoss（クラス不均衡補正の重み付き）
- **エポック数**: 30
- **バッチサイズ**: 256
- **データ分割**: 90 % train / 10 % validation (seed=42)
- **データ拡張** (学習時):
  - Resize(256) → RandomCrop(224)
  - RandomRotation(10°)
  - RandomHorizontalFlip
  - ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2)
  - ImageNet正規化 (mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])

---

## 使用データ / Training Data

- **データセット**: [SeiyaCM/KandenAiHackathonPosture2](https://huggingface.co/datasets/SeiyaCM/KandenAiHackathonPosture2)
- **枚数**: 52,500枚の合成画像
- **生成方法**: Stable Diffusion v1.5 + ControlNet (Depth) — ベース画像の深度マップを制御信号として多様なバリエーションを生成
- **フォーマット**: Parquet (image, label, prompt)

---

## 性能・評価指標 / Performance

| 指標 | 値 |
|------|-----|
| **検証精度 (Validation Accuracy)** | **97.33 %** |
| 猫背 (slouch) 誤検知率 | **0 %**（False Positive ゼロ） |

---

## 入出力仕様 / Input & Output

### 入力 (Input)

| 名前 | 形状 | 型 | 説明 |
|------|------|-----|------|
| `image` | `(batch, 3, 224, 224)` | float32 | RGB画像。ImageNet正規化済み |

**前処理パイプライン**:
1. BGR → RGB 変換
2. 224×224 にリサイズ
3. [0, 255] → [0.0, 1.0] に正規化
4. HWC → CHW 転置
5. ImageNet正規化: `(pixel - mean) / std`
   - mean = [0.485, 0.456, 0.406]
   - std = [0.229, 0.224, 0.225]

### 出力 (Output)

| 名前 | 形状 | 型 | 説明 |
|------|------|-----|------|
| `logits` | `(batch, 4)` | float32 | 各クラスのロジット値。softmax で確率に変換 |

---

## 推論方法 / Inference

### ONNX Runtime (Python)

```python
import numpy as np
import onnxruntime as ort
import cv2

# モデルのロード
session = ort.InferenceSession("posture_classifier.onnx")

# 前処理
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(3, 1, 1)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(3, 1, 1)
CLASSES = ["good", "slouch", "chin_rest", "stretch"]

def preprocess(bgr_frame):
    rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(rgb, (224, 224))
    tensor = resized.astype(np.float32) / 255.0
    tensor = tensor.transpose(2, 0, 1)  # HWC → CHW
    tensor = (tensor - MEAN) / STD
    return tensor[np.newaxis, ...]  # (1, 3, 224, 224)

# 推論
frame = cv2.imread("test_image.jpg")
input_tensor = preprocess(frame)
logits = session.run(["logits"], {"image": input_tensor})[0]

# Softmax → クラス予測
exp = np.exp(logits - np.max(logits, axis=-1, keepdims=True))
probs = exp / exp.sum(axis=-1, keepdims=True)
class_idx = int(np.argmax(probs[0]))
print(f"Predicted: {CLASSES[class_idx]} ({probs[0][class_idx]:.2%})")
```

---

## 想定ユースケース / Intended Use

- エンジニアのリアルタイム疲労モニタリング
- オフィス環境でのウェルネス管理システム
- スマートホームとの連携による自動環境制御

## 非推奨ユースケース / Out-of-Scope Use

- 監視・プライバシー侵害を目的とした利用
- 医療診断や健康評価の根拠としての利用
- 屋外や非オフィス環境での姿勢判定
- 人事評価や勤怠管理への直接的な利用

---

## 制約・限界・バイアス / Limitations & Bias

- **合成データのみで学習**: 実際の人物写真ではなく、Stable Diffusionで生成された合成画像で学習しています。実環境の多様な照明・背景・服装条件では精度が低下する可能性があります
- **単一人物を想定**: 複数人がフレーム内に映る場合の動作は未検証です
- **カメラ角度依存**: 学習データはWebカメラの正面〜やや上方アングルを想定しています。極端な角度では精度が低下します
- **文化的バイアス**: 生成プロンプトに特定の属性（年齢、性別等）のバリエーションを含めていますが、完全な多様性は保証されません
- **4クラスのみ**: 「居眠り」「離席」等の姿勢には対応していません

---

## ライセンス / License

Apache License 2.0

---

## 関連リンク / Related Links

- **GitHub**: [SeiyaCM/kanden-ai-hackathon](https://github.com/SeiyaCM/kanden-ai-hackathon)
- **HuggingFace モデル**: [SeiyaCM/KandenAiHackathonPostureModel](https://huggingface.co/SeiyaCM/KandenAiHackathonPostureModel)
- **学習データ**: [SeiyaCM/KandenAiHackathonPosture2](https://huggingface.co/datasets/SeiyaCM/KandenAiHackathonPosture2)
