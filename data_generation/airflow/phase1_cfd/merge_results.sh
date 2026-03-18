#!/bin/bash
#SBATCH -J cfd_extract
#SBATCH -p gpu
#SBATCH -c 4
#SBATCH --mem=32G
#SBATCH -o slurm-extract-%j.out
#SBATCH --container-image=/home/team-008/nvidia+pytorch+25.11-py3.sqsh
#SBATCH --container-mounts=/home/team-008:/home/team-008

# Usage:
#   CFD_JOB=$(sbatch --parsable run_openfoam.sh)
#   sbatch --dependency=afterok:${CFD_JOB} merge_results.sh

set -euo pipefail

echo "=== Starting CFD result extraction ==="
echo "Start time: $(date)"

# Install dependencies
pip install --user fluidfoam h5py numpy

# Run extraction
cd "/home/team-008/data_generation/airflow/phase1_cfd"
python -u extract_results.py

echo "=== Extraction complete ==="
echo "End time: $(date)"

# Count completed cases
CASES_DIR="/home/team-008/data/cfd_cases"
TOTAL=$(find "${CASES_DIR}" -name ".completed" | wc -l)
echo "Total completed cases: ${TOTAL}"
