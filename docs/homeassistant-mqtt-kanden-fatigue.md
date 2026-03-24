# Home Assistant に MQTT トピック `kanden/fatigue` を購読させる手順

## 概要

Docker 上の Home Assistant（設定ディレクトリ `~/homeassistant`）で、AWS IoT Core のトピック `kanden/fatigue` を購読し、疲労度スコアをセンサーとして表示するための設定手順です。

## 構成

```
API Gateway → AWS IoT Core ←(ブリッジ)→ Mosquitto(localhost:1883) ← Home Assistant
```

Home Assistant は AWS IoT Core に直接接続できないため（クライアント証明書認証が必要）、Raspberry Pi 上の Mosquitto をブリッジとして使用します。

## 前提条件

- Raspberry Pi に Docker で Home Assistant が稼働していること
- AWS IoT Core にトピック `kanden/fatigue` へパブリッシュする仕組みがデプロイ済みであること（`iac/` の CDK スタック）

**注記（ホスト名）:** Pi を LAN 上で **`ホスト名.local`**（mDNS）として参照する場合、その名前は **Raspberry Pi OS をセットアップするときに指定したホスト名**に一致する（Raspberry Pi Imager の OS カスタマイズ等）。手順内の SSH 例 `ssh <username>@<hostname>` の `<hostname>` は、自環境の実名に読み替えること。

## 1. AWS IoT Thing・証明書の作成

Home Assistant 用の IoT Thing を作成し、証明書を発行します。

```bash
# Thing 作成
aws iot create-thing --thing-name homeassistant --region us-east-1

# 証明書・キーペア作成
aws iot create-keys-and-certificate --set-as-active --region us-east-1
# → certificateArn, certificatePem, keyPair.PrivateKey を控える

# ポリシー作成
aws iot create-policy \
  --policy-name homeassistant-policy \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {"Effect": "Allow", "Action": ["iot:Connect"], "Resource": "*"},
      {"Effect": "Allow", "Action": ["iot:Subscribe"], "Resource": "arn:aws:iot:<region>:<account-id>:topicfilter/kanden/fatigue"},
      {"Effect": "Allow", "Action": ["iot:Receive"], "Resource": "arn:aws:iot:<region>:<account-id>:topic/kanden/fatigue"}
    ]
  }' \
  --region us-east-1

# ポリシーと Thing を証明書にアタッチ
aws iot attach-policy --policy-name homeassistant-policy --target <certificateArn> --region us-east-1
aws iot attach-thing-principal --thing-name homeassistant --principal <certificateArn> --region us-east-1
```

## 2. Mosquitto のインストールとブリッジ設定

### インストール

```bash
ssh <username>@<hostname>
sudo apt-get install -y mosquitto mosquitto-clients
```

### 証明書の配置

```bash
sudo mkdir -p /etc/mosquitto/certs
# 以下のファイルを配置（IoT Thing 作成時に取得したもの）
#   /etc/mosquitto/certs/certificate.pem.crt  … クライアント証明書
#   /etc/mosquitto/certs/private.pem.key       … 秘密鍵
#   /etc/mosquitto/certs/AmazonRootCA1.pem     … Amazon Root CA 1
# Amazon Root CA 1 のダウンロード:
curl -o /etc/mosquitto/certs/AmazonRootCA1.pem https://www.amazontrust.com/repository/AmazonRootCA1.pem
sudo chown mosquitto:mosquitto /etc/mosquitto/certs/*
```

### ブリッジ設定ファイルの作成

IoT Core エンドポイントは `aws iot describe-endpoint --endpoint-type iot:Data-ATS --region us-east-1` で取得できます。

```bash
sudo tee /etc/mosquitto/conf.d/aws-iot-bridge.conf > /dev/null << 'EOF'
listener 1883
allow_anonymous true

connection aws-iot
address <iot-endpoint>:8883
bridge_cafile /etc/mosquitto/certs/AmazonRootCA1.pem
bridge_certfile /etc/mosquitto/certs/certificate.pem.crt
bridge_keyfile /etc/mosquitto/certs/private.pem.key
clientid homeassistant
bridge_protocol_version mqttv311
cleansession true
notifications false
try_private false
topic kanden/fatigue in 1
EOF
```

### Mosquitto の再起動

```bash
sudo systemctl restart mosquitto
# ログでブリッジ接続を確認
sudo cat /var/log/mosquitto/mosquitto.log | tail -10
```

`Connecting bridge (step 2)` の後にエラーが出なければ接続成功です。

## 3. Home Assistant の MQTT 統合を追加

Home Assistant の UI から設定します。

1. **設定 → デバイスとサービス → 統合を追加 → MQTT** を選択
2. 接続情報を入力:
   - Broker: `localhost`
   - ポート: `1883`
   - ユーザー名: 空欄
   - パスワード: 空欄
3. 「送信」で接続を確認

## 4. センサー定義の追加

SSH で `~/homeassistant/configuration.yaml` を編集し、以下を追記します。

```yaml
mqtt:
  sensor:
    - name: "Kanden Fatigue"
      unique_id: kanden_fatigue_mqtt
      state_topic: "kanden/fatigue"
      qos: 1
      value_template: "{{ value_json.fatigue_score }}"
```

> 既に `mqtt:` セクションがある場合は、その `sensor:` リストに追加してください。`mqtt:` キーを二重に定義しないでください。

リポジトリの `homeassistant/mqtt_kanden_fatigue.yaml` も参考にしてください。

## 5. 反映・再起動

```bash
sudo docker restart homeassistant
```

## 6. 動作確認

1. **設定 → デバイスとサービス → MQTT** で接続済みであることを確認
2. API Gateway にテストデータを送信:
   ```bash
   curl -X POST https://<api-id>.execute-api.us-east-1.amazonaws.com/v1/fatigue \
     -H "Content-Type: application/json" \
     -H "x-api-key: <api-key>" \
     -d '{"device_id":"dgx-spark-001","user_id":"engineer-001","timestamp":"2026-03-18T10:00:00+09:00","fatigue_score":0.75}'
   ```
3. **開発者ツール → 状態** で `sensor.kanden_fatigue` を検索し、値が `0.75` に更新されることを確認

## 7. 疲労度が 0.7 未満のときスタックちゃんの表情を通常に戻す

AI_StackChan2 を **同一 LAN** で動かし、HTTP で `GET /face?expression=0` できる場合の例です。

1. `configuration.yaml` にパッケージを読み込む:

   ```yaml
   homeassistant:
     packages:
       stackchan_fatigue: !include package_stackchan_fatigue.yaml
   ```

   パスは `config` からの相対パスに合わせてください（例: `!include homeassistant/package_stackchan_fatigue.yaml`）。

2. リポジトリの **`homeassistant/package_stackchan_fatigue.yaml`** を Home Assistant の `config` 配下にコピーするか、内容を貼り付けます。

3. **トリガー**: `sensor.kanden_fatigue` の値が **0.7 未満に変化したとき**（しきい値のクロス時）に `expression=0` を送信します。

4. **Docker 上の HA** で `stack-chan.local` が名前解決できない場合は、YAML 内の URL を **M5Stack の IP アドレス**に書き換えてください。

## 参考ファイル

- リポジトリ内スニペット: `homeassistant/mqtt_kanden_fatigue.yaml`
- スタックちゃん表情（0.7 未満で通常）: `homeassistant/package_stackchan_fatigue.yaml`
- Mosquitto ブリッジ設定: `homeassistant/mosquitto_aws_iot_bridge.conf`
- [MQTT Sensor（Home Assistant）](https://www.home-assistant.io/integrations/sensor.mqtt/)
- [Numeric state トリガー](https://www.home-assistant.io/docs/automation/trigger/#numeric-state-trigger)
