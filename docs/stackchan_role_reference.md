# スタックちゃん `/role`（system 文面）参照

## ホスト名

スタックちゃん実機の HTTP は **`http://stack-chan.local`**（mDNS）を前提とする。Home Assistant 用 Raspberry Pi の **`*.local` 名**（例: `rp5.local`）とは別である。なお Pi の mDNS 名は **OS イメージ書き込み時に指定したホスト名**に由来する（一例にすぎない）。

## 実機との同期

1. 同一 LAN から次を実行する（またはブラウザで `http://stack-chan.local/role_get` を開く）。

   ```bash
   curl -sS "http://stack-chan.local/role_get"
   ```

2. 返却 HTML の `<pre>` 内 JSON で、`"role": "system"` の **`content`** 文字列が、ロール設定の正である。
3. 本ファイルの「参照文面」は、上記で確認した内容に合わせて**更新**する。

## 参照文面（`role`: `system` の `content`）

**最終確認**: 2026-03-24（`GET http://stack-chan.local/role_get` に基づく）

```text
あなたは大阪のおばちゃんです。気さくで陽気で優しい性格で、相手が疲れている様子を見せると、気遣う言葉をかけます。
```

## 備考

- 設定変更は **`http://stack-chan.local/role`** のフォームから **POST `/role_set`**（本文は `text/plain`）で行う。詳細は `docs/architecture-home-assistant-stackchan.md` の「初回設定」を参照する。
- `role_get` の JSON では、`messages` 配列の構成順はファームの状態により変わりうる。再現時は常に **`role` が `system` の要素**の `content` を採用すること。
