#!/bin/bash
# 4並列ジョブ完了後にクラスごとのメタデータファイルを結合するスクリプト
#
# 使い方:
#   sbatch merge_metadata_v4.sh
#   または依存ジョブとして:
#   sbatch --dependency=afterok:${JOB1}:${JOB2}:${JOB3}:${JOB4} merge_metadata_v4.sh
#
#SBATCH -J merge_metadata_v4
#SBATCH -p gpu
#SBATCH -c 1
#SBATCH --mem=4G
#SBATCH -o slurm-merge-v4-%j.out
#SBATCH --container-image=/home/team-008/nvidia+pytorch+25.11-py3.sqsh
#SBATCH --container-mounts=/home/team-008:/home/team-008

set -euo pipefail

OUTPUT_DIR="/home/team-008/data/synthetic_dataset_v4"
MERGED="${OUTPUT_DIR}/metadata.jsonl"

echo "Merging metadata files..."
cat "${OUTPUT_DIR}"/metadata_*.jsonl > "${MERGED}"
echo "Done. Total records: $(wc -l < "${MERGED}")"
