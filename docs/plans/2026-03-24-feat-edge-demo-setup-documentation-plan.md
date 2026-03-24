---
title: エッジデモ（AWS・Home Assistant・Stack-chan）セットアップ手順ドキュメント
type: feat
status: completed
date: 2026-03-24
deepened: 2026-03-24
brainstorm: docs/brainstorms/2026-03-24-edge-demo-setup-documentation-brainstorm.md
---

<!-- markdownlint-disable MD025 -->

# エッジデモ（AWS・Home Assistant・Stack-chan）セットアップ手順ドキュメント

## Enhancement Summary

**Deepened on:** 2026-03-24  
**入力**: `deepen-plan`（並列エージェントの全面起動は省略し、ローカル調査・ランブック系ベストプラクティス・既存計画との整合で深化）

### Key Improvements

1. **ランブック品質**: 目的・前提・検証・ロールバック／切り分けの枠を計画に明示し、`how_to_demo.md` 執筆時の見出しテンプレに近づけた。
2. **運用メタデータ**: 文書ヘッダに推奨する**最終検証日・オーナー**の欄を計画に追加（チーム内でも陳腐化を防ぐ）。
3. **ギャップ拡充**: HA の**設定リロード**、**リンク鮮度**、**副作用のあるコマンド**の注意、**Mermaid レンダリング**、**ナレッジを `docs/solutions/` へ還流**する提案を追加。
4. **セキュリティ**: 「チーム内向けでもリポジトリにキーを書かない」に加え、**チャット・スクリーンショット**での漏えい防止を追記。

### New Considerations Discovered

- ランブックは**インシデント後に必ず更新**する運用と相性がよい — デモ後に `how_to_demo.md` か `docs/solutions/` を 1 行でも更新する習慣を推奨。
- **クリーン環境からの手順検証**（新規クローン・別マシン）が、プレースホルダ抜けの発見に有効。
- `docs/solutions/` が未整備のため、本デモで得た**決定打の切り分け**は別タスクで 1 ファイルでも蓄積すると再利用価値が高い。

## ブレインストームとの関係

**参照**: [`docs/brainstorms/2026-03-24-edge-demo-setup-documentation-brainstorm.md`](../brainstorms/2026-03-24-edge-demo-setup-documentation-brainstorm.md)（2026-03-24）。

**採用アプローチ**: **Approach A** — 単一のデモ実行ガイド（`docs/how_to_demo.md`）。既存の深い手順はリンクで委譲し、**全体のデータフロー**と**実行順チェックリスト**を 1 本に集約する。

**確定済みの境界**:

- **読者**: チーム内のデモ再現担当のみ（秘密情報のマスキング不要）。
- **入口**: `docs/how_to_demo.md`（`docs/edge_demo.md` は任意で短い誘導可）。

### Research Insights（ブレインストーム節）

**Best practices（ランブック・手順書）:**

- **単一目的**: 本ガイドは「エッジ〜クラウド疲労デモの再現」に限定し、別用途の手順はリンク先へ逃がす（[ランブックの要点整理](https://www.docsie.io/blog/glossary/technical-runbook/)の考え方）。
- **ヘッダメタデータ**: 冒頭に **最終動作確認日**、**想定所要時間（おおまか）**、**連絡先／オーナー** を置くと陳腐化に強い（[Runbook テンプレの要素](https://www.stew.so/blog/runbook-template-guide)）。
- **検証と成功条件**: 各フェーズ末尾に「期待する出力／UI の状態」を 1 行ずつ（[成功基準の明示](https://www.stew.so/blog/runbook-template-guide)）。

**保守:**

- デモやインシデントのあと、**手順の誤りをその場でメモし**、同週中にドキュメントへ反映する（[インシデント後の更新](https://blog.incidenthub.cloud/The-No-Nonsense-Guide-to-Runbook-Best-Practices)）。

## 調査サマリ（ローカル）

| ソース | 本計画での役割 |
| --- | --- |
| [`docs/architecture-home-assistant-stackchan.md`](../architecture-home-assistant-stackchan.md) | Stack-chan HTTP、ハードウェア（Core2 for AWS + Unit IR）、LEGO PF、使用ファーム（`feat/monologue-ha-fatigue`）、初回設定・`/role` の一次記述 |
| [`docs/homeassistant-mqtt-kanden-fatigue.md`](../homeassistant-mqtt-kanden-fatigue.md) | MQTT ブリッジ・IoT Thing・HA センサー化のソース・オブ・トゥルース |
| [`docs/stackchan_role_reference.md`](../stackchan_role_reference.md) | `/role` の system 文面例・`stack-chan.local` での同期手順 |
| [`homeassistant/package_stackchan_fatigue.yaml`](../../homeassistant/package_stackchan_fatigue.yaml) | 閾値自動化と `curl` パターン |
| [`scripts/post-fatigue-apigw-ha-test.sh`](../../scripts/post-fatigue-apigw-ha-test.sh) | クラウド→センサー→自動化のスモーク期待動作 |
| [`iac/README.md`](../../iac/README.md) | 現状は汎用 CDK 文面 — デモ手順側でスタック名・Output・リージョンの**プレースホルダ**を明示する必要あり |
| [`homeassistant/docker-compose.yml`](../../homeassistant/docker-compose.yml) | HA コンテナ例（`network_mode: host`、mDNS 解決の注意） |
| [`homeassistant/mosquitto_aws_iot_bridge.conf`](../../homeassistant/mosquitto_aws_iot_bridge.conf) | Mosquitto ↔ AWS IoT ブリッジ設定の例 |
| `docs/solutions/` | 該当ディレクトリなし（ナレッジ未登録） — **深化後の提案**: 切り分けの決定版を 1 件ずつでも追加する |

**外部調査（初版）**: ドキュメント統合のため省略。**深化**: ランブック・手順書の汎用ベストプラクティスを上記に反映。

### Research Insights（調査サマリ）

**ナレッジ管理:**

- 工程別 doc がソース・オブ・トゥルースのまま、`how_to_demo.md` は**索引＋順序＋検証**に徹すると、[検索性と一元管理の両立](https://docuscry.com/blog/engineering-runbooks-architecture-docs)に近い。

## 概要

`docs/how_to_demo.md` に、**API Gateway → AWS IoT → Mosquitto → Home Assistant → Stack-chan（HTTP + IR + LEGO PF）**のデモを**同じ順序で再現**するための手順を執筆する。図・チェックリスト・既存ドキュメントへのリンクを中心とし、**重複する長文手順は新規に増やさない**。

### Research Insights（概要）

**スキャン可能性:**

- 見出し・箇条書き・コマンドブロックを優先し、段落は「なぜこの順序か」に限定する（[スキャン可能な構成](https://www.stew.so/blog/runbook-template-guide)）。

## 問題意識 / 動機

- 手順が `homeassistant-mqtt-kanden-fatigue.md`、アーキテクチャ、スクリプトコメント等に**分散**しており、初見の担当者が**依存関係の順序**を誤りやすい。
- デモ当日に参照する**単一の入口**が空に近い（`how_to_demo.md` が未整備）。

### Research Insights（問題意識）

**トリアージ:**

- 冒頭に「**この手順を使うタイミング**」（例: フルスタック初回構築、AWS だけ再デプロイ後、HA だけ入れ替え後）を 2〜3 行で書くと、[目的と範囲の明確化](https://securebyte.space/blog/2024/runbook-checklist/)に合う。

## 提案する解決策（高レベル）

1. **`docs/how_to_demo.md` を本流として全面執筆**する（目次・アンカー付き）。
2. **Mermaid 図を 1 枚以上**（ブレインストームどおり、LAN 上の HA・Stack-chan、LEGO PF 8881/8884/8883、データの流れ）。可能なら [`docs/architecture-home-assistant-stackchan.md`](../architecture-home-assistant-stackchan.md) の図を**要約転載**し、二重管理を抑える。
3. **章立て（案）** — 実装時に見出しレベルを markdownlint に合わせて調整する。

   1. **目的・読者**。
   2. **メタデータ行（推奨）**: `最終検証日: YYYY-MM-DD` / `想定所要: 例 半日〜1 日` / `オーナー: （任意）`
   3. **エンドツーエンド概要**（Mermaid + 1 段落）。
   4. **前提条件**（AWS アカウント、Pi、同一 LAN、ツール例: `aws` CLI、Docker、PlatformIO 等 — 環境依存はプレースホルダ）。
   5. **AWS 側**（CDK デプロイの参照先、`IacStack` 等の**実名はリポジトリの `iac/` 実態に合わせて記載**または `<STACK_NAME>` 表記。`PostFatigueEndpoint`・API キー取得コマンドは `post-fatigue-apigw-ha-test.sh` 冒頭コメントと整合）。
   6. **Raspberry Pi / Home Assistant**（ホスト名: **OS イメージセットアップ時のホスト名 = mDNS の `*.local`** と注記 — [`docs/architecture-home-assistant-stackchan.md`](../architecture-home-assistant-stackchan.md) および [`docs/homeassistant-mqtt-kanden-fatigue.md`](../homeassistant-mqtt-kanden-fatigue.md) へ誘導。Mosquitto ブリッジ・`mqtt_kanden_fatigue.yaml`・`packages` 読み込み・`sensor.kanden_fatigue` の確認。**YAML 変更後は Developer Tools → YAML の再読み込みまたは再起動**をチェックリストに含める）。
   7. **Stack-chan**（ファーム取得元 URL、Core2 for AWS + Unit IR、ビルド・書き込みの参照先 README。OpenAI / VOICEVOX / STT キーと **`/role`** — 詳細はアーキテクチャ「初回設定」、文面例は [`docs/stackchan_role_reference.md`](../stackchan_role_reference.md)。HA 独り言用 `/apikey` 設定が必要なら一言リンク）。
   8. **LEGO PF**（8884/8883/8881 と公式リンク — アーキテクチャと同じ表またはリンクのみ）。
   9. **スモーク検証**（`./scripts/post-fatigue-apigw-ha-test.sh` の環境変数と期待、HA の Activity / センサー履歴、Stack-chan の発話・LEGO。`docs/assets` のスクリーンショット参照）。
   10. **トラブルシュート短表**（mDNS 不通→IP 固定、Docker 内から `stack-chan.local` 解決失敗等 — アーキテクチャ・既存ブレインストームの知見を 3〜5 行）。
   11. **ロールバック／部分巻き戻し（短く）**（例: 自動化のみ無効化、Mosquitto ブリッジ停止、API キーローテーション時の差し替え手順へのポインタ）— 完全手順は別 doc に任せ可。

4. **`docs/edge_demo.md`（任意）** — 1〜2 段落で `how_to_demo.md` へ誘導するか、未作成のままにする（YAGNI）。作成する場合も本文は最小。

### Research Insights（提案する解決策）

**副作用の明示:**

- `cdk deploy`、証明書の再発行、`configuration.yaml` 変更など**本番に影響しうる操作**は、チェックリスト上で太字または「注意」行で区別する（[副作用のあるコマンドの明示](https://blog.incidenthub.cloud/The-No-Nonsense-Guide-to-Runbook-Best-Practices)）。

**図（Mermaid）:**

- GitHub 上では Mermaid がレンダリングされるが、**ローカルプレビュー環境によっては未対応**のため、「アーキテクチャ doc に同一論理図あり」と一文添えると安全。

**検証文化:**

- 可能なら**新規クローンしたマシン**または**未キャッシュの環境**で手順を一度通す（[クリーン環境でのテスト](https://blog.incidenthub.cloud/The-No-Nonsense-Guide-to-Runbook-Best-Practices)）。

## ユーザーフローとギャップ（SpecFlow 観点）

| 観点 | 内容 |
| --- | --- |
| アクター | チーム内のデモ再現担当 |
| 事前条件 | AWS デプロイ済み、Pi に HA（Docker）と Mosquitto ブリッジ設定、Stack-chan 同一 LAN、必要 API キー・トークン取得済み |
| ハッピーパス | POST 疲労スコア → センサー更新 → 閾値自動化 → Stack-chan 発話・LEGO → 低閾値で表情リセット |
| よくある分岐 | ① AWS プロファイル未設定 → `awsume` 等。② `stack-chan.local` 解決失敗 → IP 直指定。③ センサー未生成 → MQTT トピック・JSON パス確認 |
| ドキュメント上のギャップ防止 | **実行順**を番号付きチェックリストで固定。各ステップ末尾に「確認コマンド or UI」を 1 行 |

### Research Insights（ユーザーフロー）

**分岐の扱い:**

- 分岐が増えすぎると実行時の負荷が上がるため、**「よくある分岐」は表または短い if-then 箇条書きに限定**し、レアケースはトラブルシュートへ回す（[分岐の過多を避ける](https://blog.incidenthub.cloud/The-No-Nonsense-Guide-to-Runbook-Best-Practices)）。

**追加ギャップ（実装時に 1 行でよい）:**

- `package_stackchan_fatigue.yaml` 変更後、**自動化が読み込まれたか**（UI の自動化一覧またはリロード手順）。
- MQTT センサーが **Developer Tools → States** に現れるかの確認。

## 技術的考慮事項

- **markdownlint**（見出し階層、連続空行、コードフェンス言語、表の整形）。
- **相互リンク**: 相対パスで `docs/` 内を参照（リポジトリ内閲覧で破綻しないようにする）。
- **`iac/README.md`**: デモ手順では**実スタック名が未記載**のため、プレースホルダ（`<REGION>`、`<STACK_NAME>`）と「デプロイ後に Output を確認」と明記。将来 `iac/README.md` を拡充する場合は本計画のプレースホルダと**二重記述を避け**、一方に寄せる。
- **秘匿情報**: チーム内向けでも、**コミットにキーを書かない**（環境変数・`secrets.yaml` 参照のみ）。**チャット・スクリーンショット・画面録画**にも API キーや長期トークンが映り込まないよう注意を 1 行で明記する。
- **リンク鮮度（任意）**: CI または手元で `markdown-link-check` 等をかけると、相対リンクの破損を早期検知できる。

### Research Insights（技術的考慮事項）

**品質ゲート:**

- PR 時に「`how_to_demo.md` を変更したら、**関連する既存 doc へのリンクを 1 本以上触ったか**」をセルフチェック項目に加えると、ドリフトを抑えやすい。

## 受け入れ基準

- [x] `docs/how_to_demo.md` に目次があり、**AWS → HA → Stack-chan → 検証**の順で読める。
- [x] **データ経路**が本文または Mermaid で `API Gateway` → `IoT kanden/fatigue` → `Mosquitto` → `sensor.kanden_fatigue` → 自動化 → `Stack-chan HTTP` と明示され、`scripts/post-fatigue-apigw-ha-test.sh` の期待と矛盾しない。
- [x] MQTT ブリッジの**詳細手順の重複**は避け、`docs/homeassistant-mqtt-kanden-fatigue.md` へのリンクが置かれている。
- [x] Stack-chan の**ハード・ファーム・API キー・`/role`**が手順に含め、詳細は `docs/architecture-home-assistant-stackchan.md` および `docs/stackchan_role_reference.md` に誘導されている。
- [x] **LEGO PF（8881/8883/8884）**が構成の説明またはリンクで含まれる。
- [x] **Raspberry Pi の mDNS 名**が OS セットアップ時のホスト名由来である旨が注記されている（アーキテクチャと整合）。
- [x] スモーク手順に `post-fatigue-apigw-ha-test.sh` と HA UI の確認観点が含まれる。
- [x] （推奨）**最終検証日**または「手順検証済みコミット」の言及が冒頭またはフッタにある。
- [ ] `markdownlint` 実行またはエディタ診断で、新規・変更ファイルに**新規の重大違反がない**（既存ファイルの既知警告は別タスク可）。

### Research Insights（受け入れ基準）

**受け入れの運用:**

- 「未参加メンバーが**読み上げレビュー**（手順だけ声に出して読む）で齟齬がない」ことを、任意の成功基準に加えられる（[新規メンバーによる検証](https://blog.incidenthub.cloud/The-No-Nonsense-Guide-to-Runbook-Best-Practices)）。

## 成功指標

- 未参加のチームメンバーが**ドキュメントのみ**でデモ経路の全体像と作業順を説明できる。
- デモ前レビューで「次に何をするか」が**1 ファイル**でたどれる。

### Research Insights（成功指標）

**測定:**

- デモ準備の**カレンダー時間**（初回／2 回目）をメモし、次回計画の見積もりに使うと改善ループになる。

## 依存関係とリスク

| 項目 | 内容 |
| --- | --- |
| 依存 | `iac/` の実際のスタック名・Output キー（文書とコードのズレがあると手順が空振り） |
| リスク | 環境差（リージョン、ホスト名、Stack-chan IP）が多く、プレースホルダだらけになる → **例として実値をコメントで補足**するか、チーム内 Wiki へのリンクを 1 行足す |
| リスク | 図とアーキテクチャ doc の**二重管理** → 可能な限り「詳細はアーキテクチャ」とし、how_to 側はサブセット |

### Research Insights（依存関係とリスク）

**緩和:**

- `iac/` の Output 名は**コード検索**（`PostFatigueEndpoint` 等）で一次ソースを確認し、手順に**コピペ用の CloudFormation クエリ**を載せるとドリフト検知がしやすい。

## 実装タスク（チェックリスト）

- [x] `docs/how_to_demo.md` 執筆（上記章立て・メタデータ・ロールバック短節を含む）。
- [x] （任意）`docs/edge_demo.md` に入口リンクのみ追加。
- [x] 既存 doc との**用語統一**（`sensor.kanden_fatigue`、`kanden/fatigue`、スタック URL 表記）。
- [ ] （推奨）デモ実施後、`docs/solutions/` 配下に**1 ファイル**でもよいので「今回の詰まり点と解決」を残す（次回 `deepen-plan` の入力になる）。
- [x] 最終レビュー: リンク切れ、markdownlint、ブレインストームの Key Decisions との**突合**。

### Research Insights（実装タスク）

**完了の定義:**

- 上記チェックに加え、**代表者以外が 1 通し**（またはドライラン）した記録を PR 説明に 1 行書くと、受け入れの信頼度が上がる。

## 参考リンク（内部）

- [`docs/brainstorms/2026-03-24-edge-demo-setup-documentation-brainstorm.md`](../brainstorms/2026-03-24-edge-demo-setup-documentation-brainstorm.md)
- [`docs/architecture-home-assistant-stackchan.md`](../architecture-home-assistant-stackchan.md)
- [`docs/homeassistant-mqtt-kanden-fatigue.md`](../homeassistant-mqtt-kanden-fatigue.md)
- [`docs/stackchan_role_reference.md`](../stackchan_role_reference.md)
- [`scripts/post-fatigue-apigw-ha-test.sh`](../../scripts/post-fatigue-apigw-ha-test.sh)

## 参考リンク（外部・一般論）

- [Technical Runbook — 定義とベストプラクティス（Docsie）](https://www.docsie.io/blog/glossary/technical-runbook/)
- [Runbook の実務チェックリスト（SecureByte）](https://securebyte.space/blog/2024/runbook-checklist/)
- [Runbook 運用のノンセンスなしガイド（IncidentHub）](https://blog.incidenthub.cloud/The-No-Nonsense-Guide-to-Runbook-Best-Practices)
