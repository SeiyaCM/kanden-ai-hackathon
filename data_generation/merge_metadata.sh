#!/bin/bash
# Array Job 完了後にタスクごとのメタデータファイルを結合するスクリプト
#
# 使い方:
#   JOB_ID=$(sbatch --parsable run_generation.sh)
#   sbatch --dependency=afterok:${JOB_ID} merge_metadata.sh
#
#SBATCH -J merge_metadata
#SBATCH -p gpu
#SBATCH -c 1
#SBATCH --mem=4G
#SBATCH -o slurm-merge-%j.out
#SBATCH --container-image=/home/team-008/nvidia+pytorch+25.11-py3.sqsh
#SBATCH --container-mounts=/home/team-008:/home/team-008

set -euo pipefail

cd "$(dirname "$0")"

# １つ上の階層の data フォルダ内の synthetic_dataset を指定
OUTPUT_DIR="../data/synthetic_dataset"
MERGED="${OUTPUT_DIR}/metadata.jsonl"

echo "Merging metadata files..."
cat "${OUTPUT_DIR}"/metadata_task*.jsonl > "${MERGED}"
echo "Done. Total records: $(wc -l < "${MERGED}")"
