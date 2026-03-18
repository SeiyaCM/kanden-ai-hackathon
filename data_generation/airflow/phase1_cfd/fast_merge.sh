#!/bin/bash
#SBATCH --job-name=fast_merge
#SBATCH --partition=gpu
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=8        # 8コア使って並列処理させる
#SBATCH --gres=gpu:1             # GPUノードを確保（実際はCPUを回します）
#SBATCH --output=slurm-fast-merge.out

cd /home/team-008/data/cfd_cases/

# コンテナとOpenFOAMの設定
CONTAINER=~/openfoam-v2312.sqsh
SOURCE_CMD="source /usr/lib/openfoam/openfoam2312/etc/bashrc"

# 最大並列数を設定（8コアなので4〜8くらいが適正）
MAX_JOBS=4
COUNT=0

for d in case_*; do
    echo "Merging $d in background..."
    # バックグラウンドで実行 (& をつける)
    apptainer exec --nv $CONTAINER bash -c "$SOURCE_CMD && cd $d && reconstructPar -latestTime" > /dev/null 2>&1 &
    
    COUNT=$((COUNT + 1))
    
    # MAX_JOBS分たまったら、終わるまで待つ
    if [ $((COUNT % MAX_JOBS)) -eq 0 ]; then
        wait
        echo "Progress: $COUNT / 54 cases done."
    fi
done

wait
echo "✨ All cases merged successfully at speed! ✨"
