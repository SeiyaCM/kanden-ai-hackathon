import os
import json
import argparse
from datasets import load_dataset
from sklearn.model_selection import train_test_split

def prepare_hf_dataset(output_dir, repo_id="SeiyaCM/KandenAiHackathonPosture"): # Posture を追記
    os.makedirs(output_dir, exist_ok=True)
    images_dir = os.path.join(output_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    print(f"Loading dataset from Hugging Face: {repo_id}...")
    # HFからデータセットをロード
    dataset = load_dataset(repo_id, split="train")
    
    records = []
    print("Saving images and generating metadata...")
    for i, item in enumerate(dataset):
        image = item["image"]
        label = item["label"]  # '01_good', '02_slouch' etc.
        
        # 画像を保存
        filename = f"{label}_{i:05d}.png"
        filepath = os.path.join(images_dir, filename)
        image.save(filepath)
        
        # 相対パスで記録
        records.append({
            "image_path": os.path.join("images", filename),
            "label": label
        })

    # 層化分割 (Stratified Split: 80% Train, 10% Val, 10% Test)
    labels = [r["label"] for r in records]
    train_recs, temp_recs, _, temp_labels = train_test_split(
        records, labels, test_size=0.20, stratify=labels, random_state=42
    )
    val_recs, test_recs, _, _ = train_test_split(
            temp_recs, temp_labels, test_size=0.50, stratify=temp_labels, random_state=42
    )

    # JSON出力
    splits = {"train": train_recs, "val": val_recs, "test": test_recs}
    for split_name, split_data in splits.items():
        out_file = os.path.join(output_dir, f"{split_name}.json")
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(split_data, f, indent=2)
        print(f"Saved {len(split_data)} records to {out_file}")

    print("Dataset preparation complete!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=str, required=True, help="Output directory for dataset")
    args = parser.parse_args()
    prepare_hf_dataset(args.data_dir)