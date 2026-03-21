import os
from pathlib import Path
from dotenv import load_dotenv
from huggingface_hub import HfApi

# local.env から環境変数を読み込む
load_dotenv(Path(__file__).parent / "local.env")

# 設定
REPO_ID = "SeiyaCM/KandenAiHackathonPosture"
HF_TOKEN = os.environ.get("HF_TOKEN")
DATASET_FOLDER = "/home/team-008/data/synthetic_dataset_v3"

api = HfApi(token=HF_TOKEN)

print(f"📦 Hugging Face にリポジトリ '{REPO_ID}' を作成/確認しています...")
api.create_repo(repo_id=REPO_ID, repo_type="dataset", private=False, exist_ok=True)

print("🚀 データの分割アップロードを開始します...")

# 504エラーを回避するため、upload_folderではなく、ディレクトリをスキャンして少しずつコミットする
# 以下の設定を追加します
api.upload_folder(
    folder_path=DATASET_FOLDER,
    repo_id=REPO_ID,
    repo_type="dataset",
    commit_message="Add generated dataset (batched)",
    # 🌟 複数回に分けてコミットするための魔法のオプション！
    # これを指定すると、Hugging Faceのライブラリがよしなに分割してアップロードしてくれます
    multi_commits=True,
    multi_commits_verbose=True
)

print(f"✨ 分割アップロードが完了しました！")
print(f"👉 https://huggingface.co/datasets/{REPO_ID} を確認してください！")