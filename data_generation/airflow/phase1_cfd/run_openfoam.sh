#!/bin/bash
#SBATCH -J cfd_openfoam
#SBATCH -p gpu
#SBATCH --array=0-53
#SBATCH -c 8
#SBATCH --mem=16G
#SBATCH -o slurm-cfd-%A_%a.out
#SBATCH --container-image=/home/team-008/openfoam-v2312.sqsh
#SBATCH --container-mounts=/home/team-008:/home/team-008

set -euo pipefail

CASE_LIST="/home/team-008/data/cfd_cases/case_list.txt"

# Read the case directory for this array task
CASE_DIR=$(sed -n "$((SLURM_ARRAY_TASK_ID + 1))p" "${CASE_LIST}")

if [ -z "${CASE_DIR}" ]; then
    echo "ERROR: No case directory found for task ${SLURM_ARRAY_TASK_ID}"
    exit 1
fi

echo "=== Task ${SLURM_ARRAY_TASK_ID}: Starting case ${CASE_DIR} ==="
echo "Start time: $(date)"

cd "${CASE_DIR}"

# Step 1: Generate mesh
echo "--- Running blockMesh ---"
blockMesh

# Step 2: Decompose for parallel run
echo "--- Running decomposePar ---"
decomposePar -force

# Step 3: Run solver (steady-state buoyancy-driven flow)
echo "--- Running buoyantSimpleFoam (8 processes) ---"
mpirun --oversubscribe -np 8 buoyantSimpleFoam -parallel

# Step 4: Reconstruct parallel result
echo "--- Running reconstructPar ---"
reconstructPar

# Step 5: Mark as completed
touch "${CASE_DIR}/.completed"

echo "=== Task ${SLURM_ARRAY_TASK_ID}: Case ${CASE_DIR} completed ==="
echo "End time: $(date)"
