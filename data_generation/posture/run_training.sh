#!/bin/bash
#SBATCH -J posture_train
#SBATCH -p gpu
#SBATCH --gres=gpu:1
#SBATCH -c 8
#SBATCH --mem=64G
#SBATCH -o slurm-posture-%j.out
#SBATCH --container-image=/home/team-008/nvidia+pytorch+25.11-py3.sqsh
#SBATCH --container-mounts=/home/team-008:/home/team-008

set -euo pipefail

cd /home/team-008/data_generation/posture

echo "=== Starting posture classification model training ==="
echo "Start time: $(date)"
echo "GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo 'N/A')"

# Install dependencies
pip install --user torchvision scikit-learn onnx

# Paths
DATA_DIR="/home/team-008/data/synthetic_dataset"
MODEL_DIR="/home/team-008/data/posture_model"

# Step 1: Prepare dataset (if not already done)
if [ ! -f "${DATA_DIR}/train.json" ]; then
    echo "--- Preparing dataset ---"
    python -u prepare_dataset.py --data-dir "${DATA_DIR}"
else
    echo "--- Dataset already prepared, skipping ---"
fi

# Step 2: Train model
echo "--- Starting training ---"
python -u train.py \
    --data-path "${DATA_DIR}" \
    --output-dir "${MODEL_DIR}" \
    --epochs 50 \
    --batch-size 32 \
    --lr 1e-4

# Step 3: Validate
echo "--- Validating model ---"
python -u validate_model.py \
    --checkpoint "${MODEL_DIR}/best_model.pt" \
    --data-path "${DATA_DIR}" \
    --output-dir "${MODEL_DIR}/validation"

# Step 4: Export
echo "--- Exporting model ---"
python -u export_model.py \
    --checkpoint "${MODEL_DIR}/best_model.pt" \
    --output-dir "${MODEL_DIR}/exported"

echo "=== Training pipeline complete ==="
echo "End time: $(date)"
