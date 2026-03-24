---
date: 2026-03-23
topic: stackchan-handleclient-during-playback
---

# スタックちゃん: 再生中も HTTP (`handleClient`) を回す

## What We're Building

`M5Unified_AI_StackChan` の `loop()` では、`mp3->isRunning()` が真のあいだ `mp3->loop()` のみ実行し、`server.handleClient()` は **再生が終わるまで呼ばれない**。その結果、外部（例: Home Assistant）から **`/speech` 直後に `/lego` を送っても、デバイスが再生中は次の HTTP を処理できず**、LEGO 制御が遅延またはクライアント側タイムアウトにつながる。

本件では **「TTS／MP3 再生が継続している間も、Web サーバが他リクエスト（`/lego` 等）を受け付けられる」** 挙動をゴールとする。実装はファームウェアのイベントループ方針の変更が中心で、Home Assistant 側は現行の「発話と LEGO を別 HTTP で送る」構成のまま恩恵を得られることを想定する。

## Why This Approach

次の 3 案を比較した。

### Approach A: メインループで `mp3->loop()` と `handleClient()` をインタリーブ（推奨）

再生中の分岐内でも、毎フレーム（または短い間隔で）`server.handleClient()` を呼ぶ。`mp3->loop()` は従来どおり同一ループで駆動する。

**Pros:**

- 変更が局所的で、YAGNI に合う
- 既存の `ESP32WebServer`・オーディオパイプラインを大きく組み替えない

**Cons:**

- WiFi／TCP とオーディオデコードが同一タスクで競合し、**バッファアンダーランや IR タイミングへの間接影響**の検証が必要
- **再生中に再度 `/speech` が来た場合**のポリシー（上書き・無視・キュー）を決める必要がある

**Best when:** 目的が「再生中も `/lego` 等を受け付ける」に限られ、長期は別タスク化まで不要なとき。

### Approach B: オーディオ再生を別 FreeRTOS タスクへ分離

`mp3->loop()` 相当を専用タスクに移し、メインループは `handleClient()` と UI に専念する。

**Pros:**

- 責務分離が明確で、将来の拡張（同時処理の整理）に有利なことがある

**Cons:**

- `AudioOutput`・`MP3` インスタンスのスレッド安全性・ライフサイクル整理が重い
- 本件の最小目的に対して過剰になりやすい

**Best when:** Approach A で実測上オーディオが破綻する、または複数ストリーム等が必要になるとき。

### Approach C: ファームに「発話＋LEGO」をまとめた単一エンドポイントを追加

HTTP は 1 回だけで、内部で TTS 開始と `lego_pf_submit_*` を順に実行する。

**Pros:**

- クライアントは順序保証が明確
- `handleClient` の頻度問題を迂回できる（ただし再生中の別操作は別課題）

**Cons:**

- HA の `shell_command`／OpenAPI の変更が必要
- 「再生中に別用途の API を叩く」一般問題は解消しない

**Best when:** ユースケースが常に「疲労時の固定シーケンス」だけに閉じるとき。

**推奨:** まず **Approach A** で受け入れ基準（再生中に `/lego` が即処理されること）を満たせるか検証する。問題があれば B を再検討する。

## Key Decisions

- **スコープ:** 第一目標は「MP3 再生中も `handleClient` を実行し、`/lego` 等のハンドラが動くこと」。オーディオ品質・遅延は実機で確認する。
- **優先順位:** ループ内では **`mp3->loop()` を毎回呼びつつ、その前後または同イテレーションで `handleClient` を 1 回以上** 呼ぶ方針を採る（詳細は計画フェーズで確定）。
- **重複 `/speech`:** 再生中の再入は **明示的なポリシー**が必要。既定案は **新規リクエストで前再生を停止して置き換え**、または **409 相当で拒否**のいずれか（未確定 → Open Questions）。
- **リポジトリ境界:** 実装変更は `AI_StackChan2/M5Unified_AI_StackChan` 側。本リポジトリ（`kanden-ai-hackathon`）では本ドキュメントと計画・検証手順の追記でよい。

## Open Questions

1. **再生中に `/speech` が再度呼ばれたとき**の期待動作はどれか。（上書き／無視／キュー）
2. **同時に複数 TCP クライアント**を想定するか。`ESP32WebServer` は典型的に 1 接続処理が多く、同時性の上限をどう扱うか。
3. **受け入れテスト:** 「再生開始から N 秒以内に `/lego` が効く」など、数値目標があるか。

## Resolved Questions

- （なし）

## Next Steps

実装の手順・テスト・リスク対策は **`/workflows:plan`**（または同等の計画ドキュメント）で扱う。
