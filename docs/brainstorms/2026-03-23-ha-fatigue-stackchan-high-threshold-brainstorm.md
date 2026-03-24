---
date: 2026-03-23
topic: ha-fatigue-stackchan-high-threshold
---

# 疲労度 0.7 以上でスタックちゃん発話と LEGO PF（青・pwm=7）

## What We're Building

Home Assistant が **`sensor.kanden_fatigue` が 0.7 以上**になったタイミングで、同一 LAN 上の **AI_StackChan2（`http://stack-chan.local` 等）** に対して次を行う。

1. **発話**: 固定文言「おつかれさまやなぁ。あめちゃんたべぇ」（既存の `GET /speech?say=...` パターンを想定）。
2. **LEGO Power Functions**: **`POST /lego`** の **Single PWM** で **出力 B（青）**、**`pwm=7`**（`out=b`、`ch=0`。PF では 1–7 が逆転側の段階とされる資料が一般的）。
3. **モーター停止**: 駆動開始から **15 秒後**に、同一 **`ch` / `out`** で **`pwm=0`**（フロート）を送り停止する。

既存の `homeassistant/package_stackchan_fatigue.yaml` は **0.7 未満で表情を Neutral に戻す**処理のみである。本件は **しきい値の「上側」** と **音声・IR の複合アクション**を追加する要件として位置づける。

## Why This Approach

リポジトリ調査の結果、疲労データは **MQTT `kanden/fatigue` → `sensor.kanden_fatigue`**、スタックちゃん連携は **`shell_command` + `curl` + `numeric_state`** が既採用である。実装方針は **同じパターンを拡張**するのが一貫性と YAGNI に合う。

### 検討したアプローチ

#### A. パッケージ YAML 拡張（推奨）

`shell_command` に発話用・LEGO 用の `curl` を追加し、`numeric_state` の **`above: 0.7`** 自動化で **順にサービスを呼ぶ**（または 1 本のシェルで `curl` を2回）。

- **Pros**: 既存 `package_stackchan_fatigue.yaml` と同じ運用・レビューしやすい。追加依存なし。
- **Cons**: 日本語 URL エンコードや複数 `curl` の順序はシェル文字列がやや冗長。
- **Best when**: 本番も HA 標準オートメーションで完結させたい場合（現状のアーキテクチャ doc と一致）。

#### B. `rest_command` やテンプレート統合

HTTP を HA の REST 抽象化で表現する。

- **Pros**: 意図が宣言的に読みやすい場合がある。
- **Cons**: 既存パッケージが `shell_command` 中心のため、設定スタイルが混在する。
- **Best when**: 後続で認証ヘッダや共通タイムアウトを HA 側で統一したい場合。

#### C. Node-RED / 外部スクリプト

しきい値と HTTP を HA 外でオーケストレーション。

- **Pros**: 複雑な状態機械を組みやすい。
- **Cons**: 現リポジトリの「パッケージ YAML 1 本」方針から外れ、運用コストが増えやすい。
- **Best when**: 既に Node-RED が標準の家庭/ラボの場合。

推奨は **A**。要件が「2 回の HTTP 呼び出し + しきい値」に収まるため。

## Key Decisions

- **トリガー**: `numeric_state` で `sensor.kanden_fatigue` が **0.7 以上**（既存の「未満で Neutral」と対になる **上側** の自動化を新設）。
- **発話 API**: AI_StackChan2 の **`/speech`**（`say` に文言。日本語は **`curl` の `--data-urlencode` 等でエンコード**が必要な想定）。
- **LEGO API**: **`POST /lego`**、**`ch=0`**（LEGO レシーバー側ダイヤル 1 と対応。ユーザー確定）、**`pwm=7`**、**`out=b`**（PF Single PWM のデータニブル。仕様上の向き・強さは `pwm` と `out` の組み合わせに依存）。
- **モーター停止**: 駆動コマンドの **15 秒後**に **`ch=0`・`out=b`・`pwm=0`** を **`POST /lego`** で送る（ユーザー確定。2026-03-23 に 15 秒へ調整）。実装では **`delay` + 第2 `curl`**、別オートメーション、または **`script`** の `delay` などで表現する想定。
- **実行順**: **① 発話 → ② モーター開始 → ③ 15 秒待機 → ④ モーター停止**（①②は従来どおり、③④を追加）。
- **モード**: `combo` は使わず **Single PWM** のみ（ユーザー要件に合致）。

## Resolved Questions

- **チャンネル `ch`**: **`0` で確定**（2026-03-23 ユーザー回答）。`POST` 例: `ch=0&pwm=7&out=b`。
- **モーター停止タイミング**: **開始から 15 秒後**に `pwm=0` で停止（2026-03-23 ユーザー回答。駆動時間は同日 15 秒に確定）。停止 `POST` 例: `ch=0&pwm=0&out=b`。

## Open Questions

1. **再トリガー抑制**: スコアが 0.7 付近で上下する場合、**クールダウン**（例: 10 分に 1 回まで）や **`for:` で連続成立**など、**連続発火の扱い**をどうするか。
2. **`stack-chan.local` 到達性**: Docker HA 等では mDNS が効かない場合があるため、**IP 固定や `configuration.yaml` 用の変数化**を行うか。

## Next Steps

実装の手順・検証項目は **`/workflows:plan`**（または同等の計画フェーズ）に委ねる。
