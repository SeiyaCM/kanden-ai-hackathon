#!/bin/bash
#SBATCH -J hf_upload
#SBATCH -p gpu
#SBATCH -c 2
#SBATCH --mem=8G
#SBATCH -o slurm-upload-%j.out
#SBATCH --container-image=/home/team-008/nvidia+pytorch+25.11-py3.sqsh
#SBATCH --container-mounts=/home/team-008:/home/team-008

echo "=== Installing dependencies ==="
pip install --user python-dotenv huggingface_hub

echo "=== Starting Upload ==="
cd /home/team-008/data_generation/airflow
python upload_to_hf.py

echo "=== Upload Completed ==="
