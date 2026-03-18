import os
from pathlib import Path
from dotenv import load_dotenv
from huggingface_hub import HfApi

# local.env から環境変数を読み込む
load_dotenv(Path(__file__).parent / "local.env")

REPO_ID = os.environ["HF_REPO_ID"]
HF_TOKEN = os.environ["HF_TOKEN"]

# アップロードしたいデータがあるフォルダのパス
DATASET_FOLDER = "/home/team-008/data/synthetic_dataset"

api = HfApi(token=HF_TOKEN)

print(f"📦 Hugging Face にリポジトリ '{REPO_ID}' を作成/確認しています...")
# リポジトリを作成（ハッカソンのデータなので、安全のため最初は private=True にしておきます）
api.create_repo(repo_id=REPO_ID, repo_type="dataset", private=True, exist_ok=True)

print("🚀 データのアップロードを開始します（数分かかります）...")
# フォルダの中身（画像とmetadata.jsonl）を丸ごとアップロード
api.upload_folder(
    folder_path=DATASET_FOLDER,
    repo_id=REPO_ID,
    repo_type="dataset"
)

print("✨ アップロードが完了しました！Hugging Faceのサイトを確認してください！")