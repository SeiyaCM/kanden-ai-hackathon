#!/usr/bin/env bash
# API Gateway に疲労度を POST し、Home Assistant の「0.7 超え」自動化の前提となる
# sensor.kanden_fatigue のしきい値跨ぎを作るスモーク用スクリプト。
#
# 前提:
# - AWS クレデンシャル: プロファイル test は **awsume** で取得する（例: `awsume test`）。
#   bash/zsh で環境変数が付かない場合は `eval $(awsume -s test)` を使う。
# - CDK スタック出力の URL（例: https://xxxx.execute-api.ap-northeast-1.amazonaws.com/v1/fatigue）
# - API キー（x-api-key）。認証後に例えば次で取得できる:
#     aws cloudformation describe-stacks --stack-name IacStack --region <リージョン> \
#       --query "Stacks[0].Outputs[?OutputKey=='PostFatigueEndpoint'].OutputValue" --output text
#     aws apigateway get-api-key --api-key <ApiKeyId> --include-value --region <リージョン> --query value --output text
# - IoT → MQTT ブリッジ → HA が kanden/fatigue を購読し value_json.fatigue_score でセンサー化済み
#   （リポジトリの homeassistant/mqtt_kanden_fatigue.yaml 参照）
#
# 使い方:
#   awsume test
#   export KANDEN_FATIGUE_API_URL='https://YOUR_API_ID.execute-api.ap-northeast-1.amazonaws.com/v1/fatigue'
#   export KANDEN_FATIGUE_API_KEY='your-api-key-value'
#   ./scripts/post-fatigue-apigw-ha-test.sh
#
# 期待:
# - 1 回目 POST（0.5）→ 200、センサーが 0.7 未満側
# - 2 回目 POST（0.8）→ 200、numeric_state above 0.7 で「疲労度0.7以上でスタックちゃん…」が実行
#
set -euo pipefail

: "${KANDEN_FATIGUE_API_URL:?Set KANDEN_FATIGUE_API_URL (POST /fatigue のフル URL)}"
: "${KANDEN_FATIGUE_API_KEY:?Set KANDEN_FATIGUE_API_KEY (x-api-key の値)}"

post_score() {
  local score="$1"
  local body
  # API Gateway の JSON スキーマ検証に通すため、python3 で組み立てる（printf だと 400 になりうる）
  body="$(python3 -c "
import json, datetime, sys
score = float(sys.argv[1])
ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
print(json.dumps({
    'device_id': 'test-apigw-ha',
    'user_id': 'engineer-001',
    'timestamp': ts,
    'fatigue_score': score,
}))
" "$score")"

  echo "POST fatigue_score=${score} ..."
  curl -sS -w "\nHTTP %{http_code}\n" \
    -X POST "$KANDEN_FATIGUE_API_URL" \
    -H "Content-Type: application/json" \
    -H "x-api-key: ${KANDEN_FATIGUE_API_KEY}" \
    -d "$body"
  echo "---"
}

post_score "0.5"
echo "Sleep 3s (MQTT/HA 反映待ち) ..."
sleep 3
post_score "0.8"

echo "完了。Home Assistant で sensor.kanden_fatigue が 0.8 付近になり、自動化ログを確認してください。"
