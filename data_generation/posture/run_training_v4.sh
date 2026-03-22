#!/bin/bash
#SBATCH -J train_resnet_v4
#SBATCH -p gpu
#SBATCH --gres=gpu:4
#SBATCH -c 16
#SBATCH --mem=64G
#SBATCH -o logs/slurm-train-v4-%j.out
#SBATCH -e logs/slurm-train-v4-%j.err
#SBATCH --container-image=/home/team-008/nvidia+pytorch+25.11-py3.sqsh
#SBATCH --container-mounts=/home/team-008:/home/team-008

cd /home/team-008/data_generation/posture
source myenv_slouch/bin/activate

# 必要なライブラリのインストール（念のため）
pip install datasets Pillow python-dotenv huggingface_hub

# いざ、最強モデルの学習開始！
python -u train_hf.py --epochs 30 --batch-size 256 --lr 5e-4