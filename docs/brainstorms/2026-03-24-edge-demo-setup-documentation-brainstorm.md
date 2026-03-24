---
date: 2026-03-24
topic: edge-demo-setup-documentation
---

# エッジ側（Home Assistant・AWS・Stack-chan）概要とデモ用セットアップ手順ドキュメント

## What We're Building

**チーム内のデモ再現担当**が、エッジ〜クラウドの経路を把握し、**同じ条件でデモを再現**できるようにするためのドキュメントである。外部提出向けのマスキングは前提としない。対象は次の三層に限定する（「WHAT」の境界）。

1. **AWS**: 疲労スコアの取り込み経路（例: API Gateway → IoT Core → `kanden/fatigue`）。既存の `iac/` デプロイ結果と認証（API キー等）に依存する前提を明示する。
2. **Home Assistant（Raspberry Pi 上の想定）**: Mosquitto ブリッジ、`sensor.kanden_fatigue`、パッケージ自動化（閾値 0.7 と Stack-chan／LEGO）。Pi の **`*.local`（mDNS）名は OS イメージセットアップ時のホスト名**に由来することを注記する。既存の `docs/homeassistant-mqtt-kanden-fatigue.md` および `homeassistant/package_stackchan_fatigue.yaml` と整合する「実行順」を示す。
3. **Stack-chan（AI_StackChan2）**: ハードウェアは **M5Stack Core2 for AWS + Unit IR**（[Core2 for AWS](https://docs.m5stack.com/ja/core/core2_for_aws)、[Unit IR](https://docs.m5stack.com/ja/unit/ir)）。ファームウェアは **[niizawat/AI_StackChan2 の `feat/monologue-ha-fatigue`](https://github.com/niizawat/AI_StackChan2/tree/feat/monologue-ha-fatigue)**（**LEGO PF**・**HA 連携**等を追加したフォーク）。同一 LAN の HTTP API（`/speech`・`/face`・`POST /lego` 等）。`docs/architecture-home-assistant-stackchan.md` を**単一の論理参照**とし、重複は最小化する。

**スコープ外（今回）**: Raspberry Pi 上の **LLM-8850** および `docs/raspberry-pi5-qwen3-4b-llm8850.md` の内容は、デモ実行ガイドには**含めない**。必要なら別ドキュメントのみ参照する。

デモ手順の**公式入口**は **`docs/how_to_demo.md`** とする（現状はプレースホルダに近いため、計画フェーズで本文を執筆する）。`docs/edge_demo.md` は必要なら **本ガイドへの短い誘導**に留める。実装のコマンド列・検証手順の細部は **計画フェーズ（`/workflows:plan`）** に委ねる。

## Why This Approach

既存ドキュメントが**領域ごとに分割**されている（MQTT 手順、アーキテクチャ、Pi 上の HA ホスト手順など）。デモ再現には「**全体のデータフロー図**」と「**チェックリスト順のセットアップ**」が不足している。次の三案を比較する。

### Approach A: 単一の「デモ実行ガイド」（推奨）

1 本の Markdown（例: `docs/how_to_demo.md` を本流にする）に、**概要（Mermaid。同一 LAN のデータ経路に加え、スタックちゃん実機を Core2 for AWS + Unit IR とし、LEGO PF の 8881／8884／8883 物理構成まで含める）→ 前提条件 → AWS → HA → Stack-chan（ファーム書き込みに加え、OpenAI／VOICEVOX API キーと `/role` 相当のロール設定）→ スモーク検証**の順でまとめ、各節は既存ドキュメントへ**深い手順はリンク**で委譲する。

- **Pros**: デモ当日の参照が 1 ファイルで完結しやすい。重複を抑えつつ「順序」が明確。
- **Cons**: ファイルが長くなりうる（目次とアンカー必須）。
- **Best when**: 実演者がチーム内で固定され、リポジトリをクローンして同じ手順を踏む運用。

### Approach B: 「5 分クイックスタート」＋「詳細は既存 doc」

短いクイックスタート（1 ページ）と、詳細索引（`docs/edge_demo.md` 等）を分離する。

- **Pros**: レビューア向けに短文化しやすい。詳細は保守済みの doc に集約。
- **Cons**: ファイル間の役割説明を冒頭で誤解なく書く必要がある。
- **Best when**: ステークホルダ向けに「薄い」資料と、実装者向けに「厚い」資料を分けたい場合。

### Approach C: 索引のみ（新規本文は書かない）

`edge_demo.md` にリンク集とチェックリストだけを置き、本文は一切増やさない。

- **Pros**: 保守コスト最小。
- **Cons**: 「実行順」や前提の統合説明が弱く、初見のデモ担当が迷いやすい。

**推奨は A**。デモ再現の主目的は「順序と依存関係の可視化」であり、YAGNI の観点でも B の二重構造は必須ではない。長文化は**目次＋リンク**で抑える。

## Key Decisions

- **データ経路の「正」**: `API Gateway POST` → `IoT kanden/fatigue` → `Mosquitto ブリッジ` → `HA sensor` → `自動化` → `Stack-chan HTTP` を、ドキュメント上の**ハッピーパス**として明示する（`scripts/post-fatigue-apigw-ha-test.sh` の期待動作と整合）。
- **重複方針**: MQTT ブリッジの AWS CLI 手順などは `docs/homeassistant-mqtt-kanden-fatigue.md` を**ソース・オブ・トゥルース**とし、デモガイドでは要約＋リンクに留める。
- **Stack-chan 論理**: HTTP エンドポイント一覧とセキュリティ注意は `docs/architecture-home-assistant-stackchan.md` に集約し、デモガイドでは**疎通確認用 URL のみ**記載する。
- **検証の明示**: デモ成立の判定として、少なくとも「センサー値の更新」と「閾値自動化の発火」（Activity ログ）および Stack-chan 側の反応をチェックリスト化する想定とする（`docs/assets` のスクリーンショット参照可）。
- **`iac/README.md`**: 現状は CDK テンプレの汎用文面のため、デモ文書では**実スタック名・主要 Output・リージョン**を別途明記する必要がある（計画で具体化）。
- **読者**: **チーム内の再現担当のみ**。実コマンド・環境変数・エンドポイント例をそのまま記載してよい（リポジトリが非公開／アクセス制御下である前提）。外部配布用の別版はスコープ外。
- **入口ファイル**: **`docs/how_to_demo.md`** をデモ実行ガイドの正とする。`docs/edge_demo.md` は任意で、本ファイルへのリンクのみでもよい。
- **LLM-8850**: **`docs/how_to_demo.md` の対象外**。`docs/raspberry-pi5-qwen3-4b-llm8850.md` は参照用にリポジトリに残してもよいが、デモ手順本文では扱わない。
- **スタックちゃん実機ハードウェア**: デモ用**構成図**に **M5Stack Core2 for AWS** と **Unit IR** を含める。公式ドキュメント: [Core2 for AWS](https://docs.m5stack.com/ja/core/core2_for_aws)、[Unit IR](https://docs.m5stack.com/ja/unit/ir)（論理・図の一次記述は `docs/architecture-home-assistant-stackchan.md`）。
- **スタックちゃんファームウェア**: デモ・手順の前提は **[niizawat/AI_StackChan2 — `feat/monologue-ha-fatigue`](https://github.com/niizawat/AI_StackChan2/tree/feat/monologue-ha-fatigue)**（LEGO PF・HA 連携など拡張済み）。`docs/how_to_demo.md` にも取得元 URL を明記する。
- **スタックちゃん設定手順の必須項目**: `docs/how_to_demo.md` のスタックちゃん節に、**OpenAI API キー**・**Web 版 VOICEVOX API キー**の設定（`apikey.txt` または **`/apikey`**）、**STT 用キー**（利用 STT に応じる）、および **OpenAI 用ロール（システムプロンプト相当、`/role`）** の手順を含める。詳細は `docs/architecture-home-assistant-stackchan.md` の「初回設定」を一次記述とする。**`/role` の転記例・同期手順**は **`docs/stackchan_role_reference.md`**（実機は **`http://stack-chan.local`**。`rp5.local` 等の別ホストと混同しない）。
- **LEGO Power Functions 物理構成**: デモ用**構成図**に、**IR 受信機 8884 + M モーター 8883 + 電池ボックス 8881** の 3 点を含める。公式製品ページは次のとおり（`docs/how_to_demo.md` でも参照可、論理・図の一次記述は `docs/architecture-home-assistant-stackchan.md`）。
  - [IR Receiver 8884](https://www.lego.com/en-us/product/lego-power-functions-ir-receiver-8884)
  - [M Motor 8883](https://www.lego.com/en-us/product/lego-power-functions-m-motor-8883)
  - [Battery Box 8881](https://www.lego.com/en-us/product/lego-power-functions-battery-box-8881)

## Resolved Questions

1. **読者の主対象**（2026-03-24）: **チーム内の再現担当のみ**とする。外部レビュー用のマスキング方針はドキュメント要件に含めない。
2. **入口ファイル名**（2026-03-24）: **`docs/how_to_demo.md`** を本流とする。`docs/edge_demo.md` は補助（短い誘導）可。
3. **LLM-8850 の扱い**（2026-03-24）: **ドキュメント対象外**とする。疲労→HA→Stack-chan のデモ再現手順には含めない。

## Next Steps

- `/workflows:plan` に渡し、`docs/how_to_demo.md` の章立て・ファイル配置・チェックリスト項目・図の有無を実装計画に落とす。
- 計画承認後、既存 Markdown の markdownlint 準拠と相互リンクの整合を確認する。
