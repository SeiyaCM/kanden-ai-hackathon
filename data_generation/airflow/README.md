# 室内気流シミュレーション (CFD) + Physics-ML サロゲートモデル

OpenFOAM で室内気流の教師データを生成し、PINNs ベースのサロゲートモデルを学習するパイプライン。

## 概要

1. **Phase 1 (CFD)**: OpenFOAM で 54 パターンの室内気流シミュレーションを実行し、風速・圧力・温度・CO2 濃度の教師データを生成
2. **Phase 2 (Physics-ML)**: Physics-Informed Neural Networks (PINNs) でナビエ・ストークス方程式を損失関数に組み込んだサロゲートモデルを学習
3. **デプロイ**: ONNX 形式でエクスポートし、DGX Spark 上でリアルタイム推論

## 前提条件

- HPC クラスタへのアクセス (SLURM + Enroot/Pyxis)
- NVIDIA RTX A5000 GPU
- OpenFOAM v2312 コンテナ
- PyTorch コンテナ (`/home/team-008/nvidia+pytorch+25.11-py3.sqsh`)
- Python 3.10+

## サーバーアクセス

### A5000 クラウドサーバー (データ生成・学習用)

```bash
# SSH 接続
ssh a5000
```

#### インタラクティブモード (デバッグ・動作確認用)

```bash
srun -p gpu --gres=gpu:1 -c 8 --mem=48G \
  --container-image=/home/team-008/nvidia+pytorch+25.11-py3.sqsh \
  --container-mounts=/home/team-008:/home/team-008 \
  --pty bash
```

#### バッチモード (本番実行)

```bash
sbatch <script.sh>           # ジョブの投入
squeue -u $USER              # 実行状況の確認
scancel <JOB_ID>             # ジョブの中止
```

### GX Spark (エッジ推論・Home Assistant 統合)

```bash
# SSH 接続
ssh user@gx-spark.local

# 推論実行
python inference_spatial_brain.py --device cuda
```

---

## ディレクトリ構成

```
airflow/
├── README.md                  # 本ファイル
├── requirements.txt           # Python 依存パッケージ
├── local.env                  # HF_TOKEN 等 (gitignored)
├── upload_to_hf.py            # Hugging Face アップロード
│
├── phase1_cfd/                # Phase 1: CFD データ生成
│   ├── room_config.py         # 部屋形状・パラメータグリッド定義
│   ├── generate_stl.py        # 家具 STL 自動生成 (numpy-stl)
│   ├── generate_cases.py      # OpenFOAM ケースディレクトリ生成
│   ├── run_openfoam.sh        # SLURM バッチ (CFD 実行)
│   ├── extract_results.py     # OpenFOAM 出力 → HDF5
│   ├── merge_results.sh       # SLURM バッチ (結果統合)
│   └── templates/             # OpenFOAM Jinja2 テンプレート
│
└── phase2_modulus/            # Phase 2: サロゲートモデル
    ├── prepare_dataset.py     # HDF5 → 学習用データ変換
    ├── train_surrogate.py     # PINNs モデル学習
    ├── run_training.sh        # SLURM バッチ (学習実行)
    ├── export_model.py        # ONNX エクスポート
    └── validate_model.py      # 精度検証
```

## シミュレーション条件

- **部屋サイズ**: 6m x 5m x 2.7m (小規模オフィス)
- **メッシュ**: ~50K セル (1ケース約10分)
- **ソルバ**: buoyantSimpleFoam (定常、浮力考慮)
- **乱流モデル**: k-epsilon

### パラメータ化された条件 (54 ケース)

| パラメータ | 値 |
|-----------|-----|
| エアコン風速 | 1.0, 3.0, 5.0 m/s |
| エアコン温度 | 20, 24, 28 °C |
| 換気量 | 0.0, 0.05, 0.1 m³/s |
| 窓の開閉 | 閉, 開 |
| 家具レイアウト | 1 パターン (4名) |

---

## 手順

### Step 0: コンテナ準備 (初回のみ)

```bash
# A5000 サーバーに接続
ssh a5000

# OpenFOAM コンテナを取得
enroot import docker://opencfd/openfoam-run:2312
mv opencfd+openfoam-run+2312.sqsh /home/team-008/openfoam-v2312.sqsh
```

### Step 1: 依存パッケージのインストール

```bash
# A5000 サーバー上で (ssh a5000 後に実行)
cd data_generation/airflow
pip install -r requirements.txt
```

### Step 2: `local.env` の設定

```bash
cd data_generation/airflow
cp local.env local.env.bak
# local.env を編集し、HF_TOKEN に実際のトークンを設定
```

### Step 3: 家具 STL ファイル生成

```bash
cd data_generation/airflow/phase1_cfd
python generate_stl.py
# → phase1_cfd/stl/ に STL ファイルが生成される
```

### Step 4: OpenFOAM ケースディレクトリ生成

```bash
cd data_generation/airflow/phase1_cfd

# デフォルト出力先: data/cfd_cases/
python generate_cases.py

# クラスタ上で出力先を指定する場合:
OUTPUT_BASE=/home/team-008/data/cfd_cases python generate_cases.py
```

生成されるもの:
- `cfd_cases/case_0000/` 〜 `cfd_cases/case_0053/` (各ケースの OpenFOAM ディレクトリ)
- `cfd_cases/case_list.txt` (ケースパス一覧)

### Step 5: CFD シミュレーション実行

```bash
cd data_generation/airflow/phase1_cfd

# 全 54 ケースを SLURM アレイジョブで実行
CFD_JOB=$(sbatch --parsable run_openfoam.sh)
echo "CFD Job ID: ${CFD_JOB}"

# CFD 完了後に結果を HDF5 に変換 (依存ジョブ)
sbatch --dependency=afterok:${CFD_JOB} merge_results.sh
```

ジョブの確認:
```bash
squeue -u $(whoami)
# 各ケースのログ: slurm-cfd-{JOB_ID}_{TASK_ID}.out
```

### Step 6: データセットの確認

```bash
python -c "
import h5py
f = h5py.File('/home/team-008/data/cfd_dataset/airflow_dataset.h5', 'r')
print(f'Cases: {len(f.keys())}')
case = f['case_0000']
print(f'Coords shape: {case[\"coords\"].shape}')
print(f'Velocity shape: {case[\"velocity\"].shape}')
f.close()
"
```

### Step 7: サロゲートモデル学習

```bash
cd data_generation/airflow/phase2_modulus

# SLURM ジョブとして学習を実行 (データ前処理 + 学習)
sbatch run_training.sh
```

学習パラメータ:
- エポック数: 300
- バッチサイズ: 4096
- 学習率: 1e-3 (CosineAnnealing)
- Physics loss weight: 0.1

#### 2GPU 並列ハイパーパラメータ探索 (オプション)

A5000×2基を活用し、異なるハイパラで同時学習:

```bash
cd data_generation/airflow/phase2_modulus
bash run_dual_training.sh
# V1: lr=1e-3, physics_weight=0.1
# V2: lr=5e-4, physics_weight=0.05
# → 完了後に validate_model.py で精度の良い方を採用
```

### Step 8: モデル検証

```bash
cd data_generation/airflow/phase2_modulus

srun --gres=gpu:1 \
     --container-image=/home/team-008/nvidia+pytorch+25.11-py3.sqsh \
     --container-mounts=/home/team-008:/home/team-008 \
     python validate_model.py
```

出力:
- `validation/metrics.json` - RMSE, 相対L2誤差, MAE, 最大誤差
- `validation/validation_scatter.png` - 予測 vs 真値の散布図
- `validation/validation_errors.png` - 誤差分布ヒストグラム

### Step 9: モデルエクスポート

```bash
cd data_generation/airflow/phase2_modulus

srun --container-image=/home/team-008/nvidia+pytorch+25.11-py3.sqsh \
     --container-mounts=/home/team-008:/home/team-008 \
     python export_model.py
```

出力:
- `exported/airflow_surrogate.onnx` - ONNX 形式 (TensorRT 推論用)
- `exported/airflow_surrogate.pt` - TorchScript 形式

### Step 10: Hugging Face アップロード

```bash
cd data_generation/airflow
python upload_to_hf.py
```

### Step 11: GX Spark へのデプロイ

```bash
# ONNX モデルを GX Spark に転送 (ローカル PC から実行)
scp -r a5000:/home/team-008/data/airflow_model/exported/ ./local_model/
scp local_model/airflow_surrogate.onnx user@gx-spark.local:~/models/

# GX Spark に接続して推論を実行
ssh user@gx-spark.local
python inference_spatial_brain.py --device cuda
```

---

## データ転送

### A5000 → ローカル PC

ローカル PC の PowerShell から実行します。

```powershell
# CFD データセットのダウンロード
scp -r a5000:/home/team-008/data/cfd_dataset/ ./local_dataset/

# 学習済みモデルのダウンロード
scp -r a5000:/home/team-008/data/airflow_model/ ./local_model/
```

### A5000 → Hugging Face

A5000 サーバー上で実行します。

```bash
cd data_generation/airflow
python upload_to_hf.py
```

### ローカル → GX Spark

```bash
# ONNX モデルを GX Spark にデプロイ
scp exported/airflow_surrogate.onnx user@gx-spark.local:~/models/
```

---

## データ形式

### HDF5 データセット (`airflow_dataset.h5`)

```
airflow_dataset.h5
├── case_0000/
│   ├── coords      (n_cells, 3)  float32  # x, y, z [m]
│   ├── velocity    (n_cells, 3)  float32  # u, v, w [m/s]
│   ├── pressure    (n_cells,)    float32  # [Pa]
│   ├── temperature (n_cells,)    float32  # [K]
│   ├── co2         (n_cells,)    float32  # [volume fraction]
│   └── attrs:
│       ac.speed, ac.temperature, window.is_open,
│       furniture.layout_id, ventilation.rate
├── case_0001/
│   ...
```

### サロゲートモデル入出力

**入力** (8次元):
- `x, y, z` - 空間座標 (正規化済み)
- `ac_speed` - エアコン風速
- `ac_temp` - エアコン温度
- `window_open` - 窓開閉 (0/1)
- `layout_id` - 家具レイアウト ID
- `ventilation_rate` - 換気量

**出力** (6次元):
- `u, v, w` - 風速ベクトル
- `p` - 圧力
- `T` - 温度
- `CO2` - CO2 濃度

**派生出力** (後処理):
- 淀み指標 = 1 / (|velocity| + epsilon)
- CO2 滞留傾向 = 局所CO2 / 平均CO2

---

## トラブルシューティング

### OpenFOAM が収束しない
- `slurm-cfd-*.out` のログで残差を確認
- `fvSolution` の緩和係数を下げる (例: U 0.5, p_rgh 0.2)
- `controlDict` の endTime を増やす

### メモリ不足
- `run_openfoam.sh` の `--mem` を増やす
- メッシュ解像度を下げる (`blockMeshDict.j2` の nx, ny, nz)

### 学習の損失が下がらない
- `--physics-weight` を下げる (例: 0.01)
- `--lr` を下げる (例: 5e-4)
- データの正規化を確認 (`normalization.json`)

### enroot import が失敗する
- Docker Hub のレート制限の可能性。時間をおいて再試行
- プロキシ設定を確認

### インタラクティブデバッグ
- SLURM ジョブが失敗する場合、インタラクティブモードで手動実行して原因を特定:
```bash
srun -p gpu --gres=gpu:1 -c 8 --mem=48G \
  --container-image=/home/team-008/nvidia+pytorch+25.11-py3.sqsh \
  --container-mounts=/home/team-008:/home/team-008 \
  --pty bash
# コンテナ内で手動コマンド実行してエラーを再現
```
