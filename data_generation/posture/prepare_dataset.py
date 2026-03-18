"""
Prepare the synthetic posture dataset for training.

Reads metadata.jsonl, splits into train/val/test (80/10/10),
and saves split files as JSON for the training pipeline.
"""

import os
import json
import argparse

import numpy as np


LABEL_MAP = {
    "01_good": 0,
    "02_slouch": 1,
    "03_chin_rest": 2,
    "04_stretch": 3,
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../data/synthetic_dataset"))


def load_metadata(data_dir):
    """Load metadata.jsonl and return list of records."""
    metadata_path = os.path.join(data_dir, "metadata.jsonl")
    records = []
    with open(metadata_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            # Verify image exists
            img_path = os.path.join(data_dir, record["file_name"])
            if not os.path.exists(img_path):
                print(f"Warning: image not found, skipping: {record['file_name']}")
                continue
            records.append({
                "file_name": record["file_name"],
                "label": record["label"],
                "label_id": LABEL_MAP[record["label"]],
            })
    return records


def split_dataset(records, train_ratio=0.8, val_ratio=0.1, seed=42):
    """Split records into train/val/test sets with stratification."""
    rng = np.random.RandomState(seed)

    # Group by label for stratified split
    by_label = {}
    for r in records:
        by_label.setdefault(r["label"], []).append(r)

    train, val, test = [], [], []
    for label, items in sorted(by_label.items()):
        indices = rng.permutation(len(items))
        n_train = int(len(items) * train_ratio)
        n_val = int(len(items) * val_ratio)

        for i in indices[:n_train]:
            train.append(items[i])
        for i in indices[n_train:n_train + n_val]:
            val.append(items[i])
        for i in indices[n_train + n_val:]:
            test.append(items[i])

    return train, val, test


def main():
    parser = argparse.ArgumentParser(description="Prepare posture dataset splits")
    parser.add_argument("--data-dir", type=str, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Output directory for split files (default: same as data-dir)")
    args = parser.parse_args()

    output_dir = args.output_dir or args.data_dir
    os.makedirs(output_dir, exist_ok=True)

    print(f"Loading metadata from: {args.data_dir}")
    records = load_metadata(args.data_dir)
    print(f"Total valid records: {len(records)}")

    train, val, test = split_dataset(records)

    # Summary
    print(f"\nSplit sizes: train={len(train)}, val={len(val)}, test={len(test)}")
    print("\nClass distribution:")
    for split_name, split_data in [("train", train), ("val", val), ("test", test)]:
        counts = {}
        for r in split_data:
            counts[r["label"]] = counts.get(r["label"], 0) + 1
        print(f"  {split_name}: {dict(sorted(counts.items()))}")

    # Save splits
    for split_name, split_data in [("train", train), ("val", val), ("test", test)]:
        path = os.path.join(output_dir, f"{split_name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(split_data, f, indent=2, ensure_ascii=False)
        print(f"Saved {path} ({len(split_data)} records)")

    # Save label map
    label_map_path = os.path.join(output_dir, "label_map.json")
    with open(label_map_path, "w", encoding="utf-8") as f:
        json.dump(LABEL_MAP, f, indent=2)
    print(f"Saved {label_map_path}")

    print("\nDataset preparation complete.")


if __name__ == "__main__":
    main()
