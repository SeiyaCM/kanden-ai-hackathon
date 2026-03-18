#!/bin/bash
# =============================================================================
# 2GPU並列ハイパーパラメータ探索
#
# A5000×2基を使い、異なるハイパラ設定で同時に学習を実行。
# 精度の良い方のモデルを採用する。
#
# 使い方:
#   bash run_dual_training.sh
#   # → 2つのSLURMジョブが投入される
#   # → 完了後、validate_model.py で両方のモデルを比較
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PREPARED_DIR="/home/team-008/data/cfd_dataset/prepared"

# --- 設定 V1: アグレッシブ (高学習率, 強い物理制約) ---
echo "=== Submitting V1: lr=1e-3, physics_weight=0.1 ==="
JOB1=$(sbatch --parsable \
    -J pinn_v1 \
    -p gpu \
    --gres=gpu:1 \
    -c 8 \
    --mem=64G \
    -o slurm-pinn-v1-%j.out \
    --container-image=/home/team-008/nvidia+pytorch+25.11-py3.sqsh \
    --container-mounts=/home/team-008:/home/team-008 \
    --wrap="cd ${SCRIPT_DIR} && \
        pip install --user h5py numpy && \
        python -u train_surrogate.py \
            --data-path ${PREPARED_DIR} \
            --output-dir /home/team-008/data/airflow_model_v1 \
            --epochs 300 \
            --batch-size 4096 \
            --lr 1e-3 \
            --physics-weight 0.1")
echo "  Job ID: ${JOB1}"

# --- 設定 V2: 保守的 (低学習率, 弱い物理制約) ---
echo "=== Submitting V2: lr=5e-4, physics_weight=0.05 ==="
JOB2=$(sbatch --parsable \
    -J pinn_v2 \
    -p gpu \
    --gres=gpu:1 \
    -c 8 \
    --mem=64G \
    -o slurm-pinn-v2-%j.out \
    --container-image=/home/team-008/nvidia+pytorch+25.11-py3.sqsh \
    --container-mounts=/home/team-008:/home/team-008 \
    --wrap="cd ${SCRIPT_DIR} && \
        pip install --user h5py numpy && \
        python -u train_surrogate.py \
            --data-path ${PREPARED_DIR} \
            --output-dir /home/team-008/data/airflow_model_v2 \
            --epochs 300 \
            --batch-size 4096 \
            --lr 5e-4 \
            --physics-weight 0.05")
echo "  Job ID: ${JOB2}"

echo ""
echo "=== Both jobs submitted ==="
echo "Monitor with: squeue -u \$(whoami)"
echo "Compare results after completion:"
echo "  python validate_model.py --model-path /home/team-008/data/airflow_model_v1/best_model.pt"
echo "  python validate_model.py --model-path /home/team-008/data/airflow_model_v2/best_model.pt"
