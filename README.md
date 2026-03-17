# kanden-ai-hackathon
**Kanden hackathon team NANIWA-Factory**

本プロジェクトは、エンジニアの「身体的・精神的な疲労」と「室内の物理的な環境」をマルチモーダルAIでリアルタイムに解析し、最適な作業空間を自動制御する **「空間AIブレイン」** です。

単なる「室温が上がったらエアコンをつける」というルールベースの制御ではなく、以下の高度な処理をローカル環境（DGX Spark）とクラウドGPU（A5000）のハイブリッド構成で実現します。

- **マルチモーダル疲労検知**: カメラ（姿勢崩れ）とマイク（「疲れた」「分らん！」などのネガティブ発言）からエンジニアのストレスを検知
- **AI流体シミュレーション (Physics-ML)**: CO2の滞留や空気の流れ（気流）をAIが物理演算に基づき予測
- **自律的空間制御**: LLMが状況を総合的に判断し、[Home Assistant](https://www.home-assistant.io/) を通じてエアコン、サーキュレーター、照明などを最適な状態へ自動制御

---

## 🛠️ 技術要素

本システムは、最先端のオープンソース技術と強力なGPUコンピューティングを組み合わせて構築されています。

| 技術 | ライブラリ / フレームワーク | 用途 |
|------|--------------------------|------|
| 音声認識 (ASR) | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | マイクからの音声をリアルタイム（超低遅延）でテキスト化し、ネガティブワードを抽出 |
| 物理情報NN (PINNs) | [Physics-NeMo](https://github.com/NVIDIA/physicsnemo) | 室内気流・CO2滞留のAIシミュレーション（CFD）モデルを構築 |
| 画像生成・姿勢推定 | Stable Diffusion + ControlNet | データ不足を補うため、エンジニアの疲労姿勢を再現した合成データセットを錬成 |
| スマートホーム連携 | [Home Assistant](https://www.home-assistant.io/) + MCP | センサーデータの取得と家電制御をLLMからMCP経由でシームレスかつセキュアに実行 |

### ハードウェア構成

| 役割 | 環境 |
|------|------|
| 推論 (Local) | DGX Spark（リアルタイム処理・LLM推論） |
| 学習・錬成 (Cloud) | NVIDIA RTX A5000（合成データの生成、Physics-NeMoの学習） |

---

## 📊 学習データ

AIの精度を高めるため、A5000の圧倒的な計算力を活かして独自のデータセットを構築しました。

### エンジニア姿勢合成データセット: [SeiyaCM/KandenAiHackathon](https://huggingface.co/datasets/SeiyaCM/KandenAiHackathon)

現場エンジニアの様々な姿勢（集中、頭を抱える等）をControlNet (Depth) を用いて100バリエーションずつ生成した、計4,200枚の高品質な画像データセット。

### 空間気流・環境データセット *(構築中)*

[Physics-NeMo](https://github.com/NVIDIA/physicsnemo) を用いて生成された「温度・CO2濃度・気流」の相関関係を示す物理シミュレーションデータ。

---

## 🏗️ システムアーキテクチャ

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
    SD -->|"4200枚Upload"| HF
    HF -.->|"Fine-tuning"| Vision
    Train_PINN -.->|"モデルDeploy"| PINN
```
