import os
from pathlib import Path
from dotenv import load_dotenv
from huggingface_hub import HfApi

# local.env から環境変数を読み込む
load_dotenv(Path(__file__).parent / "local.env")

REPO_ID = os.environ["HF_REPO_ID"]
HF_TOKEN = os.environ["HF_TOKEN"]

# アップロード対象
CFD_DATASET_FOLDER = "/home/team-008/data/cfd_dataset"
MODEL_FOLDER = "/home/team-008/data/airflow_model"

api = HfApi(token=HF_TOKEN)

print(f"Hugging Face にリポジトリ '{REPO_ID}' を作成/確認しています...")
api.create_repo(repo_id=REPO_ID, repo_type="dataset", private=True, exist_ok=True)

# CFD データセット (HDF5 + case_index.csv) をアップロード
print("CFD データセットのアップロードを開始します...")
api.upload_folder(
    folder_path=CFD_DATASET_FOLDER,
    path_in_repo="airflow/dataset",
    repo_id=REPO_ID,
    repo_type="dataset",
    ignore_patterns=["prepared/**"],  # 前処理済みnpyは除外
)

# 学習済みモデルをアップロード
print("学習済みモデルのアップロードを開始します...")
api.upload_folder(
    folder_path=MODEL_FOLDER,
    path_in_repo="airflow/model",
    repo_id=REPO_ID,
    repo_type="dataset",
    ignore_patterns=["checkpoint_*.pt"],  # 中間チェックポイントは除外
)

print("アップロードが完了しました！")
