#!/bin/bash
#SBATCH -J pinn_train
#SBATCH -p gpu
#SBATCH --gres=gpu:1
#SBATCH -c 8
#SBATCH --mem=64G
#SBATCH -o slurm-pinn-%j.out
#SBATCH --container-image=/home/team-008/nvidia+pytorch+25.11-py3.sqsh
#SBATCH --container-mounts=/home/team-008:/home/team-008

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd /home/team-008/data_generation/airflow/phase2_modulus

echo "=== Starting PINNs surrogate model training ==="
echo "Start time: $(date)"
echo "GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo 'N/A')"

# Install dependencies
pip install --user h5py numpy

# Step 1: Prepare dataset (if not already done)
PREPARED_DIR="/home/team-008/data/cfd_dataset/prepared"
if [ ! -f "${PREPARED_DIR}/train/inputs.npy" ]; then
    echo "--- Preparing dataset ---"
    python -u prepare_dataset.py
else
    echo "--- Dataset already prepared, skipping ---"
fi

# Step 2: Train model
echo "--- Starting training ---"
python -u train_surrogate.py \
    --data-path "${PREPARED_DIR}" \
    --output-dir /home/team-008/data/airflow_model \
    --epochs 300 \
    --batch-size 4096 \
    --lr 1e-3 \
    --physics-weight 0.1

echo "=== Training complete ==="
echo "End time: $(date)"
