---
license: mit
language:
  - ja
  - en
tags:
  - image-classification
  - posture-detection
  - synthetic-data
  - stable-diffusion
  - controlnet
size_categories:
  - 10K<n<100K
task_categories:
  - image-classification
---

# KandenAiHackathonPosture2 — エンジニア姿勢合成画像データセット

> **English Summary**
> A large-scale synthetic image dataset of 52,500 images depicting engineers in four sitting postures (good, slouch, chin rest, stretch). Generated using Stable Diffusion v1.5 + ControlNet (Depth) from reference base images, with diverse variations in age, ethnicity, clothing, lighting, and camera artifacts. Designed for training posture classification models for real-time fatigue detection in office environments.

---

## データセット概要

本データセットは、**空間AIブレイン** プロジェクトのために構築された、エンジニアの座り姿勢を再現した大規模合成画像データセットです。

実際のオフィスでの撮影データ収集が困難なため、画像生成AI（Stable Diffusion v1.5 + ControlNet Depth）を用いて、ベース画像の姿勢構造を保持しながら多様なバリエーションを自動生成しました。

---

## データの内容

| 項目 | 詳細 |
|------|------|
| **件数** | 52,500枚 |
| **フォーマット** | Parquet（自動変換済み） |
| **データ分割** | train: 52,500行 |
| **サイズ** | 約69.3 GB |

### カラム説明

| カラム名 | 型 | 説明 |
|---------|-----|------|
| `image` | Image (JPEG) | 合成生成された姿勢画像 |
| `label` | string | 姿勢クラスラベル（`01_good`, `02_slouch`, `03_chin_rest`, `04_stretch`） |
| `prompt` | string | 画像生成に使用したプロンプト（年齢、服装、環境等の詳細記述） |

### クラス説明

| ラベル | 説明 | 学習時のID |
|--------|------|-----------|
| `01_good` | 正しい姿勢でデスクワーク中。背筋が伸び、モニターを正面から見ている | 0 |
| `02_slouch` | 猫背で前傾した疲労姿勢。肩が丸まり、顔がモニターに近い | 1 |
| `03_chin_rest` | 頬杖をついている姿勢。片手で顎を支え、ストレスや集中力低下を示す | 2 |
| `04_stretch` | ストレッチ・伸びをしている姿勢。腕を後ろに伸ばし、休憩行動を示す | 3 |

---

## 作成方法

### 生成パイプライン

1. **ベース画像の撮影**: 各姿勢クラスの典型的なポーズを撮影
2. **深度マップ抽出**: MiDaS (Depth Estimator) でベース画像から深度マップを生成
3. **ControlNet生成**: Stable Diffusion v1.5 + ControlNet (Depth) で深度マップを制御信号として、多様なバリエーションを生成

### 使用モデル

| コンポーネント | モデル |
|-------------|--------|
| 画像生成 | `runwayml/stable-diffusion-v1-5` |
| ControlNet | `lllyasviel/sd-controlnet-depth` |
| 深度推定 | MiDaS (`lllyasviel/Annotators`) |
| スケジューラ | UniPCMultistepScheduler |

### 生成パラメータ

| パラメータ | 値 |
|-----------|-----|
| 推論ステップ数 | 20 |
| Guidance Scale | 7.5 |
| バリエーション数 | ベース画像1枚あたり100枚 |

### プロンプト例

- **good**: `"A professional Japanese engineer working with good posture, bright modern office, highly detailed, 4k"`
- **slouch**: `"A tired Japanese engineer slouching over a laptop, messy dark room, glowing monitor light, exhausted, cinematic lighting"`
- **chin_rest**: `"A stressed Japanese engineer resting chin on hand, looking at laptop screen, server room background, deep thought, highly detailed"`
- **stretch**: `"A Japanese engineer stretching arms back, relaxing on a desk chair, taking a break, coding environment"`

### ネガティブプロンプト

```
worst quality, low quality, bad anatomy, bad hands, missing fingers, deformed, ugly, cropped, real person face
```

---

## 使用方法

### Python (datasets ライブラリ)

```python
from datasets import load_dataset

dataset = load_dataset("SeiyaCM/KandenAiHackathonPosture2")
print(dataset)
# DatasetDict({
#     train: Dataset({
#         features: ['image', 'label', 'prompt'],
#         num_rows: 52500
#     })
# })

# 画像の表示
sample = dataset["train"][0]
sample["image"].show()
print(f"Label: {sample['label']}")
print(f"Prompt: {sample['prompt']}")
```

### 学習での使用例

```python
from datasets import load_dataset
from torchvision import transforms

dataset = load_dataset("SeiyaCM/KandenAiHackathonPosture2")
split = dataset["train"].train_test_split(test_size=0.1, seed=42)

label_map = {"01_good": 0, "02_slouch": 1, "03_chin_rest": 2, "04_stretch": 3}

transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])
```

---

## 想定ユースケース

- エンジニアの姿勢分類モデルの学習・評価
- オフィス環境でのウェルネスモニタリングシステムの開発
- 合成データによる画像分類の研究・実験
- ControlNet を用いたデータ拡張手法のベンチマーク

---

## 注意点・制約・バイアス / Limitations & Bias

- **合成画像**: 全画像がStable Diffusionで生成されたものであり、実際の写真ではありません。実環境での評価には実データでの追加検証が推奨されます
- **プロンプト由来のバイアス**: 生成プロンプトにバリエーション（年齢、性別、服装等）を含めていますが、生成モデル自体のバイアスが反映される可能性があります
- **姿勢の明確性**: 一部の生成画像では、指定した姿勢が明確に表現されていない場合があります
- **解像度**: 生成画像はWebカメラ品質を模しており、高解像度な用途には適しません
- **環境の多様性**: オフィス環境を中心に生成しており、自宅や屋外環境のバリエーションは限定的です

---

## ライセンス / License

MIT License

---

## 関連リンク / Related Links

- **GitHub**: [SeiyaCM/kanden-ai-hackathon](https://github.com/SeiyaCM/kanden-ai-hackathon)
- **学習済みモデル**: [SeiyaCM/KandenAiHackathonPostureModel](https://huggingface.co/SeiyaCM/KandenAiHackathonPostureModel)（ResNet18 → ONNX、検証精度 97.33 %）
