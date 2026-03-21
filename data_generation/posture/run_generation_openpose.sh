#!/bin/bash
#SBATCH -J posture_gen_v3
#SBATCH -p gpu
#SBATCH --gres=gpu:1
#SBATCH -c 8
#SBATCH --mem=32G
#SBATCH -o slurm-gen-v3-%j.out
#SBATCH --container-image=/home/team-008/nvidia+pytorch+25.11-py3.sqsh
#SBATCH --container-mounts=/home/team-008:/home/team-008

set -euo pipefail

cd /home/team-008/data_generation/posture

echo "=== Starting OpenPose Image Generation ==="

# 1. 仮想環境の作成と起動
python -m venv myenv
source myenv/bin/activate

# 2. パッケージの徹底管理
pip install --upgrade pip
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install diffusers transformers accelerate mediapipe==0.10.21

# 🌟 OpenCVの「競合」を完全に排除してHeadless版のみを入れる
pip uninstall -y opencv-python opencv-contrib-python opencv-python-headless opencv-contrib-python-headless
pip install opencv-python-headless opencv-contrib-python-headless

# 3. モデルの事前キャッシュ（修正済み）
python -c "
from diffusers import ControlNetModel, StableDiffusionControlNetPipeline
import torch
cnet = ControlNetModel.from_pretrained('lllyasviel/sd-controlnet-openpose', torch_dtype=torch.float16)
StableDiffusionControlNetPipeline.from_pretrained('runwayml/stable-diffusion-v1-5', controlnet=cnet, torch_dtype=torch.float16)
"

# 4. 画像生成スクリプトの実行
python -u generate_dataset_openpose.py

deactivate
echo "=== Generation pipeline complete ==="