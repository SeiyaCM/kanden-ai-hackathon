---
title: AI_StackChan2 再生中も HTTP サーバを処理する（handleClient インタリーブ）
type: feat
status: active
date: 2026-03-23
deepened: 2026-03-23
brainstorm: docs/brainstorms/2026-03-23-stackchan-handleclient-during-playback-brainstorm.md
---

<!-- markdownlint-disable MD025 -->

# AI_StackChan2 再生中も HTTP サーバを処理する（`handleClient` インタリーブ）

## Enhancement Summary

**Deepened on:** 2026-03-23  
**Sections enhanced:** 調査サマリ、問題定義、提案する解決策、技術的考慮事項、受け入れ基準・成功指標、依存関係とリスク、実装タスク、参考  
**Research sources:** Web 検索（ESP32 `WebServer`／オーディオ共存、ESP8266Audio バッファ・アンダーラン）、ローカル `main.cpp` 該当行の確認、`docs/solutions/`（該当なし）

### Key Improvements

1. **現行コード位置の特定**: `mp3->isRunning()` と `server.handleClient()` の分岐を **行番号付き**で計画に紐づけた。
2. **オーディオ優先の根拠**: ESP8266Audio 系では **`mp3->loop()` の呼び出し間隔が長いとアンダーラン・途切れ**が起きやすい、というコミュニティ知見をリスクと検証項目に反映した。
3. **`handleClient` の性質**: 同期 `WebServer` では **`loop` からの頻繁な `handleClient()`** が応答性の前提である旨を明文化し、**ハンドラ内の長時間処理**が残るボトルネックになりうる点を追記した。
4. **エスカレーション経路の具体化**: Approach A で音が破綻する場合の **DMA バッファ調整**・**別タスク化（Approach B）**・**AsyncWebServer への移行**を「将来オプション」として整理した（MVP では採用しない）。

### New Considerations Discovered

- 同一タスクでインタリーブしても、**HTTP ルートハンドラがブロッキング**なら再び他リクエストが遅延するため、**`/lego` 等がキューに積むだけか**を実装レビューで確認する価値がある。
- **ウォッチドッグ／`loop` 占有**: メインタスクでデコードと HTTP を両立する場合、**他の協調的タスクへの譲り**（短い `delay` や `yield` の妥当性）はボード・コア数に依存し、実測が必要。

## ブレインストームとの関係

**参照**: `docs/brainstorms/2026-03-23-stackchan-handleclient-during-playback-brainstorm.md`（2026-03-23）。

ブレインストームで確定した内容:

- **課題**: `mp3->isRunning()` が真の間、`server.handleClient()` が呼ばれず、**再生中は `/lego` 等の HTTP が処理されない**。
- **推奨アプローチ**: **Approach A** — メイン `loop()` 内で `mp3->loop()` と `handleClient()` を**同一イテレーションでインタリーブ**する（最小変更）。
- **エスカレーション**: 実測でオーディオが破綻する場合のみ **Approach B**（再生を別 FreeRTOS タスクへ）を再検討。

未確定（ブレインストーム Open Questions）: 再生中の再 `/speech` ポリシー、同時クライアント想定、数値 SLA。本計画では **MVP 用の暫定既定**を記載し、実装前にプロダクト側で確定する。

## 調査サマリ（ローカル＋深化）

| ソース | 内容 |
| ------ | ---- |
| ブレインストーム（上記） | Approach A/B/C の比較と推奨 |
| `docs/architecture-home-assistant-stackchan.md` | HA から `/speech` と `POST /lego` を別リクエストで送る構成。疲労パッケージは **発話直後に LEGO** を叩くため、ファーム側の受付停止がボトルネックになりうる |
| `docs/solutions/` | 該当ナレッジなし |
| `AI_StackChan2/.../main.cpp`（実測行番号） | 1370–1386 行付近: `mp3->isRunning()` 真の間は `mp3->loop()` と `delay(1)` のみ、**偽のときだけ** `server.handleClient()` |

**外部調査（深化）**: ESP32 の同期 `WebServer` では `handleClient()` を **メインループで繰り返し呼ぶ**設計が一般的。オーディオと同居する場合、**一方が他方を長時間ブロック**するとストリーミング品質や HTTP 応答が両方悪化するため、**インタリーブ順序・各イテレーションの最大処理時間**が実務上の焦点になる。コミュニティでは **オーディオを別タスクに分離**する提案も多いが、本件はブレインストームどおり **まず Approach A** で様子見する。

**リポジトリ境界**: ソース変更は **`AI_StackChan2`**（本ワークスペース `kanden-ai-hackathon` 外の想定パス: `../AI_StackChan2/...`）。本リポジトリでは **本計画書と、必要ならアーキテクチャ文書の一行注記**にとどめる。

### Research Insights（調査サマリ）

**Best practices:**

- `handleClient()` は **呼び出し頻度**が HTTP 応答性に直結する（放置すると接続がキューに滞留する）。
- ESP8266Audio 利用例では、**`loop()` 間が数十 ms 以上空く**とアンダーランが目立つ、という報告があり、**インタリーブ後も `mp3->loop()` を毎イテレーション欠かさない**ことが重要。

**References:**

- [ESP32 WebServer Library – handleClient()](https://avantmaker.com/references/esp32-arduino-core-index/esp32-webserver-library/esp32-webserver-library-handleclient)（`handleClient` の役割の説明）
- [ESP8266Audio Issue #270（DMA バッファと再生完了）](https://github.com/earlephilhower/ESP8266Audio/issues/270)（バッファ設計変更時の挙動）
- [ESP8266Audio バッファ／アンダーランに関する議論の要約（検索経由）](https://github.com/earlephilhower/ESP8266Audio/issues)（プロジェクト Issue 一覧）

## SpecFlow 補足（ユーザー導線と隙）

| フロー | 期待 | リスク・ギャップ |
| ------ | ---- | ---------------- |
| HA: `/speech` → 続けて `POST /lego` | 発話が長くても **LEGO ハンドラが遅延なく実行**される | 現状は再生終了まで `handleClient` が不在 |
| 再生中に再度 `/speech` | ポリシーに応じて一貫した挙動 | 未確定のため **クラッシュ・二重デコード**を避けるガードが必要 |
| 再生中に複数回 `POST /lego` | 既存のキュー（`LegoPF` ワーカー）が順処理 | HTTP 層が詰まらなければ現行設計と整合しやすい |
| TTS 終了後 | マイク再開・モード復帰は現行どおり | インタリーブ後も **終了処理ブロック**の実行順を維持する |

## 問題定義

Home Assistant 等から **短い間隔で複数 HTTP**（例: 発話 API の直後に LEGO API）を送ったとき、ファームウェアが **MP3 再生中に TCP/HTTP を処理しない**ため、2 本目以降が **再生完了までブロック**され、自動化の `delay` やクライアントタイムアウトと組み合わさって **意図したタイミングで IR が出ない**ことがある。

### Research Insights（問題定義）

**実装根拠（コード位置）:**

現状、次の構造により **再生中は HTTP が進まない**（`AI_StackChan2/M5Unified_AI_StackChan/src/main.cpp` 1370–1386 行付近）。

- `mp3->isRunning()` が真: `mp3->loop()`、終了時クリーンアップ、`delay(1)`。
- 偽: `server.handleClient()`。

本改修の「WHAT」は、この **排他を解き、再生中も `handleClient()` を実行する**ことである。

## 提案する解決策（高レベル）

1. **`loop()` の `mp3->isRunning()` 真の分岐内**でも、**毎回（または毎イテレーション 1 回）`server.handleClient()` を呼ぶ**。
2. **`mp3->loop()`** は従来どおり呼び続け、**オーディオバッファ供給を欠かさない**順序（典型的には `mp3->loop()` の後に `handleClient()`、またはその逆を 1 サイクルで両方実行）を実機で確認して確定する。
3. **再生中の再 `/speech`** について、MVP 既定を次のいずれかに決めて実装する（ブレインストームの未確定を解消）:
   - **推奨（安全寄り）**: 再生中は **HTTP 503 または簡易 JSON で拒否**し、クライアントはリトライ可能にする。
   - **代替（UX 寄り）**: 既存ストリームを **明示的に `stop` してから** 新 TTS を開始（再入時の `file` ポインタと `M5.Speaker` 状態に注意）。

### Research Insights（提案する解決策）

**実装順序の検証指針（疑似コードレベル、確定は実機）:**

- 各 `loop` イテレーションで **両方**実行する: 例として「`mp3->loop()` → `server.handleClient()`」のように、**オーディオ供給を先に確保**してから HTTP を処理する順序を第一候補とする。
- `delay(1)` の要否は、**WiFi スタックへの譲り**と**音の安定**のトレードオフとして残し、悪化時のみ `delay(0)` 相当の検討や回数削減を行う。

**中長期オプション（MVP では採用しない）:**

- **AsyncWebServer**: コールバック駆動で `loop` 詰まりを緩和しうるが、**既存ルートの移植コスト**が大きい。Approach A/B で不足のときの選択肢として記録する。
- **別タスクで `audio.loop()`**（ブレインストーム Approach B）: コミュニティでも「同一ループだと相互ブロック」とされる場面がある。実測で Approach A が不合格のときに移行する。

## 技術的考慮事項

- **同一タスクでの CPU 共有**: WiFi スタックと MP3 デコードが競合し、**ノイズ・途切れ**が出る可能性。`delay(1)` の要否や `yield` 相当の扱いは実測で調整。
- **`ESP32WebServer`**: 多くの例と同様、**`loop` から定期的な `handleClient`** が前提。別タスクへサーバだけ移す案はスコープ外（Approach B 時に検討）。
- **LEGO IR**: 既存の **別タスク／キュー**（`LegoPF`）と組み合わせると、HTTP 受付が復活すれば **CPU 並列性**は維持しやすい。
- **再入とリソース**: `Voicevox_tts` 開始経路と `mp3` 停止クリーンアップの **二重呼び出し**でヒープ破損しないよう、フラグまたはガードを検討。

### Research Insights（技術的考慮事項）

**パフォーマンス／品質:**

- ESP8266Audio まわりでは **DMA バッファ個数・サイズ**が音切れとトレードオフになる報告がある。Approach A で途切れが出る場合、**バッファパラメータ調整**を Approach B より前に試す価値がある（過大はパニック報告あり。変更は小刻みに）。

**HTTP ハンドラの非ブロッキング性:**

- `handleClient()` を呼んでも、**個別ルートのハンドラが重い**と次のリクエストは依然として遅れる。`/lego` が **キュー投入のみ**で早期リターンしているかを確認し、必要なら計画に「ハンドラの最大処理時間」のレビュー項目を追加する。

**同時接続:**

- 同期 `WebServer` は **1 クライアント処理中に次が待つ**ことがある。HA が **直列に `curl` を発行**する現行パターンとは相性がよい。ブラウザの複数タブ同時操作は **MVP 外**でもよいが、Open Question として残す。

## 受け入れ基準

- [ ] **MP3 再生中**に `POST /lego`（および既存の他エンドポイント）が **再生完了を待たずに**ハンドラまで到達し、**LEGO キューにジョブが積まれる**（実機でシリアルログまたは IR 受信で確認）。
- [ ] **通常の TTS 再生**（数秒〜数十秒）で、**実用上許容できる範囲**の音切れ・ノイズがない（主観 + 可能なら波形／耳視聴の記録）。
- [ ] **TTS 終了後**のマイク再開・表情リセット・モード復帰が **従来と同等**に動く。
- [ ] 再生中の **再 `/speech`** について、選んだポリシー（拒否または停止して置換）が **文書化どおり**に動き、**再起動を要しない異常状態**に入らない。

### Research Insights（受け入れ基準）

**計測のすすめ:**

- **HTTP 側**: 再生開始直後に `POST /lego` を送り、**レスポンスまでの時間**と **IR 動作開始**のタイムスタンプをログに記録する（スマートフォン秒表＋シリアルでも可）。
- **オーディオ側**: 改修前後で同一クリップを再生し、**途切れ回数の主観比較**を記録する（AB テスト）。

## 成功指標

- 疲労自動化相当のシーケンス（`/speech` 直後に `POST /lego`）で、**発話が最後まで流れている間にも LEGO が指定秒数以内に動作**する（目安: **5 秒以内**に IR 送信開始。ブレインストームの数値 SLA が確定したらここを置換）。
- 連続運用（1 時間程度）で **ウォッチドッグ・再起動・ヒープ異常**がない。

### Research Insights（成功指標）

- **5 秒以内**は暫定。HA の `shell_command` タイムアウトや `curl` の `--max-time` があれば、**それより十分短い**ことを確認すると運用で破綻しにくい。

## 依存関係とリスク

| 項目 | 内容 |
| ---- | ---- |
| 依存 | PlatformIO ビルド環境、対象ボード（Core2 / CoreS3 等）の実機 |
| リスク | オーディオ品質劣化 → **DMA バッファ調整** → なお悪い場合 **Approach B** |
| リスク | 再入バグ → コードレビューと再生中 `/speech` の明示ポリシー |
| リスク | HA 側が同一接続でパイプラインする場合の挙動 → 現状は **別 `curl` 呼び出し**が一般的で影響小 |
| リスク | **ハンドラ内ブロッキング** → `handleClient` を増やしても改善しない → ルート実装の見直し |

### Research Insights（依存関係とリスク）

**ロールバック:**

- 変更は `loop` 分岐に集中する想定のため、**従来の if/else 排他に戻す**だけでロールバック可能にしておくと検証が速い（ブランチまたはコメントブロックで可）。

## 実装タスク（チェックリスト）

ファーム（`AI_StackChan2/M5Unified_AI_StackChan`）:

- [x] `main.cpp` の **`mp3->isRunning()` 分岐**（約 1370–1386 行）を改修し、**`server.handleClient()` を再生中も実行**する（再生有無にかかわらず毎ループ `handleClient` を 1 回呼ぶ形に統一）。
- [x] **`mp3->loop()`** の呼び出し頻度を維持。呼び順は **`mp3->loop()`（再生中のみ）→ `delay(1)` → `handleClient()`** で実装。音質が悪い場合は Research Insights に従い順序・`delay` を調整する。
- [x] 再生中 **`GET /speech`** は **HTTP 503**（`Service Unavailable: TTS playing`）で拒否。`mp3` は `server.begin()` より前に `new` し、HTTP 受付と整合させた。
- [x] **HTTP ルートハンドラ**（`/lego`）は **キュー投入のみ**であることをレビュー済み（変更なし）。
- [x] ビルド確認: `pio run`（環境 `m5stack-core2`）成功。既存の M5Unified 非推奨警告のみ。
- [ ] 実機スモーク: 再生中 `POST /lego`、再生完了後のウェイクワードモード、連続トリガ、**1 時間**程度の連続稼働（**未実施・運用で実施**）。

本リポジトリ（`kanden-ai-hackathon`）:

- [x] `docs/architecture-home-assistant-stackchan.md` にファーム改修の挙動（再生中も HTTP、再 `/speech` は 503）を追記した。
- [ ] 本計画の **`status`** は、実機スモーク完了後に `completed` へ更新する（現状はコード・ドキュメントまで完了）。

### Research Insights（実装タスク）

**検証の優先順位（提案）:**

1. インタリーブのみ（ポリシーは「再生中 `/speech` は 503」など最小）
2. 音問題が出たら `delay(1)`／呼び順の微調整
3. それでも不可なら DMA バッファ検討
4. 最後の手段として Approach B 設計メモを別ドキュメント化

## 参考

- ブレインストーム: `docs/brainstorms/2026-03-23-stackchan-handleclient-during-playback-brainstorm.md`
- アーキテクチャ: `docs/architecture-home-assistant-stackchan.md`
- 関連 HA 計画（発話＋LEGO シーケンス）: `docs/plans/2026-03-23-feat-ha-fatigue-stackchan-high-threshold-plan.md`
- upstream 参考: [AI_StackChan2](https://github.com/robo8080/AI_StackChan2)、[AI_StackChan2_README](https://github.com/robo8080/AI_StackChan2_README)
- 外部（深化）: [ESP32 WebServer `handleClient`](https://avantmaker.com/references/esp32-arduino-core-index/esp32-webserver-library/esp32-webserver-library-handleclient)、[ESP8266Audio #270](https://github.com/earlephilhower/ESP8266Audio/issues/270)
