# Space AI Brain — エンジニア疲労検知 & 作業空間自動制御

**Kanden AI Hackathon — Team NANIWA-Factory**

> **English Summary**
> A multi-modal AI system that detects engineer fatigue in real time through posture recognition and physics-based airflow simulation, then automatically controls the workspace (AC, fans, lights) via Home Assistant. Powered by a custom 52,500-image synthetic dataset, a ResNet18 classifier (97.33 % val accuracy), and an NVIDIA Physics-NeMo CFD surrogate model — all running as lightweight ONNX models on DGX Spark.

---

本プロジェクトは、エンジニアの「身体的・精神的な疲労」と「室内の物理的な環境」をマルチモーダルAIでリアルタイムに解析し、最適な作業空間を自動制御する **「空間AIブレイン」** です。

単なる「室温が上がったらエアコンをつける」というルールベースの制御ではなく、以下の高度な処理をローカル環境（DGX Spark）とクラウドGPU（A5000）のハイブリッド構成で実現します。

- **マルチモーダル疲労検知**: カメラ（姿勢崩れ）とマイク（「疲れた」「分らん！」などのネガティブ発言）からエンジニアのストレスを検知
- **AI流体シミュレーション (Physics-ML)**: CO2の滞留や空気の流れ（気流）をAIが物理演算に基づき予測
- **自律的空間制御**: LLMが状況を総合的に判断し、[Home Assistant](https://www.home-assistant.io/) を通じてエアコン、サーキュレーター、照明などを最適な状態へ自動制御

---

## 主な機能 / Features

| 機能 | 説明 |
|------|------|
| リアルタイム姿勢分類 | Webカメラ映像から4姿勢（良好・猫背・頬杖・ストレッチ）を分類し疲労度を算出 |
| AI気流シミュレーション | 物理NNサロゲートモデルで室内の温度・CO2・気流を瞬時に予測 |
| 統合疲労スコアリング | 姿勢(70 %) + 環境(30 %) を統合し 0.0〜1.0 の疲労度を算出 |
| スマートホーム自動制御 | AWS IoT Core → Home Assistant 経由でエアコン・照明等を最適制御 |
| マルチプロバイダ推論 | TensorRT > CUDA > CPU を自動選択し、最速の推論環境で実行 |

---

## 🛠️ 技術スタック / Tech Stack

| 技術 | ライブラリ / フレームワーク | 用途 |
|------|--------------------------|------|
| 姿勢分類 | ResNet18 + ONNX Runtime | Webカメラ映像からエンジニア姿勢を4クラス分類 |
| 物理情報NN (PINNs) | [Physics-NeMo](https://github.com/NVIDIA/physicsnemo) | 室内気流・CO2滞留のAIシミュレーション（CFD）モデルを構築 |
| 画像生成・データ錬成 | Stable Diffusion v1.5 + ControlNet (Depth) | データ不足を補うため、疲労姿勢を再現した52,500枚の合成データセットを錬成 |
| 音声認識 (ASR) | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | マイクからの音声をリアルタイムでテキスト化し、ネガティブワードを抽出 |
| UIダッシュボード | Streamlit | リアルタイム疲労モニタリング画面 |
| スマートホーム連携 | [Home Assistant](https://www.home-assistant.io/) + MCP | センサーデータの取得と家電制御をLLMからMCP経由で実行 |
| クラウド中継 | AWS API Gateway + IoT Core (CDK) | 疲労データの受信とMQTTパブリッシュ |

### ハードウェア構成

| 役割 | 環境 |
|------|------|
| 推論 (Local) | DGX Spark（リアルタイム処理・LLM推論） |
| 学習・錬成 (Cloud) | NVIDIA RTX A5000 × 4 GPU（合成データ生成、Physics-NeMo学習） |

---

## 🤖 モデル情報 / Models

### 姿勢分類モデル — Posture Classifier

| 項目 | 詳細 |
|------|------|
| アーキテクチャ | ResNet18 (torchvision pretrained → Full fine-tuning) |
| 学習環境 | NVIDIA RTX A5000 × 4 GPU (DataParallel) |
| 検証精度 | **97.33 %**（猫背の誤検知ゼロ） |
| 入力 | `(batch, 3, 224, 224)` float32 — ImageNet正規化済みRGB |
| 出力 | `(batch, 4)` logits → softmax で 4クラス確率 |
| フォーマット | ONNX (~42 MB) |
| クラス | `good`(0), `slouch`(1), `chin_rest`(2), `stretch`(3) |
| ファイル | `model/posture/posture_classifier.onnx` |
| HuggingFace | [SeiyaCM/KandenAiHackathonPostureModel](https://huggingface.co/SeiyaCM/KandenAiHackathonPostureModel) |

### 気流サロゲートモデル — Airflow Surrogate

| 項目 | 詳細 |
|------|------|
| フレームワーク | NVIDIA Physics-NeMo |
| 学習データ | OpenFOAM buoyantSimpleFoam による54ケースCFDシミュレーション |
| 入力 | `(batch, 8)` float32 — [x, y, z, ac_speed, ac_temp, window_open, layout_id, vent_rate] (MinMax正規化) |
| 出力 | `(batch, 6)` float32 — [u, v, w, p, T, CO2] (MinMax正規化 [0,1]) |
| フォーマット | ONNX |
| ファイル | `model/airflow/airflow_surrogate.onnx` |
| HuggingFace | [SeiyaCM/KandenAiHackathonAirflowModel](https://huggingface.co/SeiyaCM/KandenAiHackathonAirflowModel) |

### ロボットアーム模倣学習モデル — ACT (Candy Basket Delivery)

| 項目 | 詳細 |
|------|------|
| アルゴリズム | ACT (Action Chunking with Transformers) |
| Vision Backbone | ResNet18 (ImageNet pretrained) |
| パラメータ数 | 52M (51,597,190) |
| フレームワーク | [LeRobot](https://github.com/huggingface/lerobot) v0.4.4 |
| 学習手法 | 模倣学習（テレオペレーションデータから学習） |
| 学習ステップ | 100,000 steps |
| 最終 loss | 0.031 |
| 入力 | 関節角度 (6DoF) + 俯瞰カメラ画像 (640×480) + グリッパーカメラ画像 (640×480) |
| 出力 | 6自由度アクション指令値 |
| 推論FPS | 30Hz (CUDA) — 学習時FPSと一致させることが成功率に直結 |
| HuggingFace | [himorishige/act_so101_candy_basket](https://huggingface.co/himorishige/act_so101_candy_basket) |

---

## 📊 学習データ / Datasets

### エンジニア姿勢合成データセット

[SeiyaCM/KandenAiHackathonPosture2](https://huggingface.co/datasets/SeiyaCM/KandenAiHackathonPosture2)

| 項目 | 詳細 |
|------|------|
| 枚数 | **52,500枚** |
| フォーマット | Parquet (image, label, prompt) |
| 生成方法 | Stable Diffusion v1.5 + ControlNet (Depth) |
| クラス | `01_good`, `02_slouch`, `03_chin_rest`, `04_stretch` |
| ライセンス | MIT |

### 空間気流・環境データセット

[SeiyaCM/KandenAiHackathonAirflow](https://huggingface.co/datasets/SeiyaCM/KandenAiHackathonAirflow)

| 項目 | 詳細 |
|------|------|
| ケース数 | 54 |
| フォーマット | CSV / Parquet |
| 生成方法 | OpenFOAM buoyantSimpleFoam CFDシミュレーション |
| パラメータ | AC風速, AC温度, 窓開閉, 換気量, レイアウト |
| ライセンス | MIT |

### ロボットアーム テレオペレーションデータセット

[himorishige/so101_candy_basket](https://huggingface.co/datasets/himorishige/so101_candy_basket)

| 項目 | 詳細 |
|------|------|
| エピソード数 | 50 |
| 総フレーム数 | 29,186 |
| FPS | 30 |
| フォーマット | LeRobot v3.0（Parquet + MP4） |
| 収集方法 | テレオペレーション（SO-ARM101 リーダー・フォロワー構成） |
| カメラ | 俯瞰（Logitech C920）+ グリッパー（InnoMaker U20CAM-1080p） |
| タスク | 飴ちゃん入りカゴを掴んでユーザーへ運ぶ |
| ライセンス | Apache-2.0 |

---

## 🏗️ システムアーキテクチャ / Architecture

ローカルの最強推論環境（DGX Spark）を中心に、クラウド（A5000）で学習した知能をデプロイし、AWS API Gateway / IoT Core を中継レイヤーとして Home Assistant を制御するアーキテクチャです。

```mermaid
graph TD
    %% ユーザー環境（入力）
    subgraph RealWorld ["現実空間（入力）"]
        Cam["📷 カメラ<br/>姿勢・表情"]
        Mic["🎙️ マイク<br/>ネガティブ発言"]
        Sensors["🌡️ Home Assistant<br/>温度/CO2/気流センサー"]
    end

    %% 推論環境（ローカル）
    subgraph LocalEnv ["DGX Spark (Local AI Brain)"]
        Agent["⚡ エージェントループ<br/>イベント駆動・LLM起動制御"]
        Vision["👁️ 画像認識モデル<br/>姿勢判定"]
        Whisper["👂 faster-whisper<br/>音声テキスト化"]
        LLM["🧠 ローカルLLM<br/>統合判断・制御計画"]
        PINN["🌪️ Physics-NeMo (推論)<br/>気流・環境予測"]
    end

    %% 連携層（出力専用）
    subgraph BridgeLayer ["連携プロトコル（出力）"]
        MCP["🔌 MCP Server<br/>(制御指示の送信)"]
    end

    %% AWSクラウド層
    subgraph AWSCloud ["AWS Cloud"]
        APIGW["🌐 API Gateway<br/>REST API<br/>(HTTPS エンドポイント)"]
        IoTCore["☁️ AWS IoT Core<br/>MQTTブローカー"]
    end

    %% 現実空間（出力）
    subgraph Actuators ["現実空間（出力）"]
        HA_Out["🏠 Home Assistant<br/>デバイス制御"]
        AC["❄️ エアコン"]
        Fan["🌀 サーキュレーター"]
        Light["💡 スマート照明"]
    end

    %% クラウド環境（学習・データ錬成）
    subgraph CloudEnv ["A5000 (Cloud Training)"]
        SD["🎨 画像錬成<br/>Stable Diffusion"]
        Train_PINN["🧪 流体学習<br/>Physics-NeMo"]
        HF["📦 Hugging Face<br/>データセット"]
    end

    %% 1. センサーイベントをエージェントが直接受信（HA WS 非SSL）
    Sensors -->|"① subscribe_trigger<br/>(WebSocket ws://・閾値条件一致時)"| Agent

    %% 2. 映像・音声の処理
    Cam -->|"映像ストリーム"| Vision
    Mic -->|"音声ストリーム"| Whisper

    %% 3. エージェントがLLMを起動
    Agent -->|"② センサーコンテキスト通知<br/>(閾値超過時)"| LLM
    Vision -->|"姿勢・疲労状態"| LLM
    Whisper -->|"ネガティブ発言"| LLM

    %% 4. 物理シミュレーションの活用
    LLM -->|"③ 気流シミュレーション要求"| PINN
    PINN -->|"④ 空気淀み・CO2予測結果"| LLM

    %% 5. 疲労度をMCP経由でAPI GWへ送信
    LLM -->|"⑤ 疲労度スコア (0.0〜1.0)"| MCP
    MCP -->|"⑥ 疲労度データ送信<br/>(HTTPS POST)"| APIGW
    APIGW -->|"⑦ MQTTパブリッシュ<br/>(直接統合・Lambda不要)"| IoTCore
    IoTCore -->|"⑧ MQTTサブスクライブ<br/>機器制御"| HA_Out

    HA_Out --> AC
    HA_Out --> Fan
    HA_Out --> Light

    %% 6. 学習とデプロイの流れ（バックグラウンド）
    SD -->|"52,500枚Upload"| HF
    HF -.->|"Fine-tuning"| Vision
    Train_PINN -.->|"モデルDeploy"| PINN
```

---

## 📁 ディレクトリ構成 / Directory Structure

```
kanden-ai-hackathon/
├── app/                            # メインアプリケーション（推論 + UI）
│   ├── main.py                     #   Streamlit ダッシュボード
│   ├── config.py                   #   設定・正規化パラメータ
│   ├── inference/
│   │   ├── posture.py              #   姿勢分類 ONNX 推論
│   │   ├── airflow.py              #   気流サロゲート ONNX 推論
│   │   ├── fatigue.py              #   統合疲労スコアリング
│   │   └── providers.py            #   ONNX Runtime プロバイダ選択
│   ├── requirements-cpu.txt        #   CPU 環境用依存パッケージ
│   └── requirements-dgx.txt        #   DGX Spark 環境用依存パッケージ
├── data_generation/                # データ錬成・モデル学習
│   ├── posture/                    #   姿勢データ生成 & ResNet18 学習
│   │   ├── generate_dataset_depth.py   # Stable Diffusion + ControlNet 画像生成
│   │   ├── train_hf.py                 # HuggingFace データセットから学習
│   │   ├── export_model.py             # PyTorch → ONNX エクスポート
│   │   └── upload_to_hf.py            # データセットを HuggingFace にアップロード
│   └── airflow/                    #   気流データ生成 & サロゲートモデル学習
│       ├── phase1_cfd/             #     OpenFOAM CFD シミュレーション
│       └── phase2_modulus/         #     Physics-NeMo サロゲートモデル学習
├── model/                          # 学習済みモデル（ONNX + PyTorch）
│   ├── posture/                    #   posture_classifier.onnx
│   └── airflow/                    #   airflow_surrogate.onnx
├── iac/                            # AWS CDK インフラ (TypeScript)
├── docs/                           # API仕様書・ドキュメント
│   └── openapi.yml                 #   REST API 仕様 (OpenAPI 3.0)
├── LICENSE                         # Apache License 2.0
└── README.md
```

---

## 🚀 セットアップ & 起動方法 / Setup & Usage

### 前提条件

- Python 3.10+
- Webカメラ（姿勢検知用）
- 学習済みONNXモデルが `model/posture/` および `model/airflow/` に配置済みであること

### CPU版（ノートPC / 開発環境）

```bash
pip install -r app/requirements-cpu.txt
streamlit run app/main.py
```

### NVIDIA DGX Spark版（GPU推論）

CUDA 12.x がインストールされた DGX Spark 環境で実行してください。
TensorRT > CUDA > CPU の優先順で自動的に最適なプロバイダが選択されます。

```bash
pip install -r app/requirements-dgx.txt
streamlit run app/main.py
```

> **Note:** `onnxruntime` と `onnxruntime-gpu` は排他的なパッケージです。両方を同時にインストールしないでください。

### 環境変数によるプロバイダ制御

環境変数 `ONNX_DEVICE` で推論プロバイダを明示的に指定できます。

| 値 | プロバイダ優先順 | ユースケース |
|------|-----------------|-------------|
| `auto`（デフォルト） | TensorRT > CUDA > CPU | 利用可能な最速プロバイダを自動選択 |
| `dgx` | TensorRT > CUDA > CPU | DGX Spark 明示指定 |
| `cuda` | CUDA > CPU | TensorRT なしの CUDA 環境 |
| `cpu` | CPU のみ | GPU環境でのデバッグ・検証用 |

```bash
# 例: GPU搭載マシンでもCPU推論を強制
ONNX_DEVICE=cpu streamlit run app/main.py
```

### スモークテスト

モデルの読み込みと推論が正常に動作するか確認できます。

```bash
python -m app.test_inference
```

### モデルの学習（再現手順）

姿勢分類モデルをHugging Faceデータセットから再学習する場合:

```bash
# 学習（4GPU環境推奨）
python data_generation/posture/train_hf.py \
  --output-dir model/posture/validation \
  --epochs 30 \
  --batch-size 256 \
  --lr 5e-4

# ONNX エクスポート
python data_generation/posture/export_model.py
```

---

## ⚠️ 制約・注意事項 / Limitations

- **姿勢モデルは合成データのみで学習**: Stable Diffusion による生成画像で学習しているため、実環境では照明条件・カメラ角度・服装によって精度が低下する可能性があります
- **気流モデルは54ケースのCFDデータで学習**: パラメータグリッドの範囲外の条件（AC風速 > 5 m/s 等）では予測精度が保証されません
- **単一人物を想定**: 複数人がカメラに映る場合の姿勢分類は未対応です
- **ONNX Runtime バージョン**: 1.17.0 以上が必要です
- **Webカメラ必須**: 姿勢検知にはUSB/内蔵カメラが必要です
- **部屋レイアウト**: 気流モデルは 6m × 5m × 2.7m のオフィスを前提としています

---

## 📄 ライセンス / License

本プロジェクトは [Apache License 2.0](LICENSE) の下で公開されています。

This project is licensed under the [Apache License 2.0](LICENSE).
