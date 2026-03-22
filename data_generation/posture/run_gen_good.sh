#!/bin/bash
#SBATCH -J posture_gen_v4_good
#SBATCH -p gpu
#SBATCH --gres=gpu:1
#SBATCH -c 8
#SBATCH --mem=32G
#SBATCH -o slurm-gen-v4-good-%j.out
#SBATCH --container-image=/home/team-008/nvidia+pytorch+25.11-py3.sqsh
#SBATCH --container-mounts=/home/team-008:/home/team-008

set -euo pipefail

cd /home/team-008/data_generation/posture

echo "=== Starting v4 Generation: 01_good ==="

python -m venv myenv
source myenv/bin/activate

pip install --upgrade pip
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install diffusers transformers accelerate mediapipe==0.10.21

pip uninstall -y opencv-python opencv-contrib-python opencv-python-headless opencv-contrib-python-headless
pip install opencv-python-headless opencv-contrib-python-headless

python -c "
from diffusers import ControlNetModel, StableDiffusionControlNetPipeline
import torch
cnet = ControlNetModel.from_pretrained('lllyasviel/sd-controlnet-openpose', torch_dtype=torch.float16)
StableDiffusionControlNetPipeline.from_pretrained('runwayml/stable-diffusion-v1-5', controlnet=cnet, torch_dtype=torch.float16)
"

python -u generate_dataset_openpose.py --class-name 01_good --num-variations 2500

deactivate
echo "=== Generation complete: 01_good ==="
