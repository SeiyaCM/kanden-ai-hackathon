#!/bin/bash
#SBATCH -J data_synthesis
#SBATCH -p gpu
#SBATCH --array=0-1
#SBATCH --gres=gpu:1
#SBATCH -c 4
#SBATCH --mem=32G
#SBATCH -o slurm-%A_%a.out
#SBATCH --container-image=/home/team-008/nvidia+pytorch+25.11-py3.sqsh
#SBATCH --container-mounts=/home/team-008:/home/team-008

set -euo pipefail

# 🔴 修正1：スクリプトがあるディレクトリに移動（パスズレ防止）
cd "${SLURM_SUBMIT_DIR}"

echo "Starting task $SLURM_ARRAY_TASK_ID on node $SLURM_NODELIST"

# 🔴 修正2：Task 0 だけがモデルを事前ダウンロードし、他は待つ（競合回避）
# ロックファイルでジョブID単位の完了を管理（複数ジョブ実行時も干渉しない）
LOCK_FILE="$HOME/.model_cache_ready_${SLURM_ARRAY_JOB_ID}"

if [ "$SLURM_ARRAY_TASK_ID" -eq 0 ]; then
    echo "Task 0: Downloading and caching Hugging Face models..."
    python -c "
from controlnet_aux import MidasDetector
from diffusers import ControlNetModel, StableDiffusionPipeline  # ←ここを変更
import torch
MidasDetector.from_pretrained('lllyasviel/Annotators')
ControlNetModel.from_pretrained('lllyasviel/sd-controlnet-depth', torch_dtype=torch.float16)
StableDiffusionPipeline.from_pretrained('runwayml/stable-diffusion-v1-5', torch_dtype=torch.float16) # ←ここを変更
"
    touch "${LOCK_FILE}"
    echo "Task 0: Download completed. Lock file created."
else
    echo "Task $SLURM_ARRAY_TASK_ID: Waiting for Task 0 to cache models..."
    until [ -f "${LOCK_FILE}" ]; do
        sleep 10
    done
    echo "Task $SLURM_ARRAY_TASK_ID: Lock file detected. Proceeding."
fi

# 🔴 pip install はここから削除しました（実行前に手動で1回やります）

# Pythonスクリプトの実行
python -u generate_dataset_depth.py