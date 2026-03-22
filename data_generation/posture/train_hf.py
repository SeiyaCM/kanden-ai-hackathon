import os
import argparse
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import transforms, models
from datasets import load_dataset
from collections import Counter
import json

NUM_CLASSES = 4
REPO_ID = "SeiyaCM/KandenAiHackathonPosture2"

class PostureClassifier(nn.Module):
    def __init__(self, num_classes=NUM_CLASSES, pretrained=True):
        super().__init__()
        weights = models.ResNet18_Weights.DEFAULT if pretrained else None
        self.backbone = models.resnet18(weights=weights)
        in_features = self.backbone.fc.in_features
        self.backbone.fc = nn.Linear(in_features, num_classes)

    def forward(self, x):
        return self.backbone(x)

def get_transforms(is_train=True):
    if is_train:
        return transforms.Compose([
            transforms.Resize((256, 256)),
            transforms.RandomRotation(10),
            transforms.RandomCrop(224),
            transforms.RandomHorizontalFlip(),
            transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
    else:
        return transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

def train(args):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    # 1. Hugging Face からデータセットを超高速ダウンロード＆ロード
    print(f"📦 Hugging Faceからデータセット '{REPO_ID}' をロード中...")
    dataset = load_dataset(REPO_ID)
    
    # trainとvalに分割 (90% train, 10% val)
    split_dataset = dataset["train"].train_test_split(test_size=0.1, seed=42)
    train_ds = split_dataset["train"]
    val_ds = split_dataset["test"]
    print(f"Train samples: {len(train_ds)}, Val samples: {len(val_ds)}")

    label_map = {"01_good": 0, "02_slouch": 1, "03_chin_rest": 2, "04_stretch": 3}

    # 前処理関数の定義
    train_transforms = get_transforms(is_train=True)
    val_transforms = get_transforms(is_train=False)

    def preprocess_train(examples):
        images = [train_transforms(image.convert("RGB")) for image in examples["image"]]
        labels = [label_map.get(l, 0) if isinstance(l, str) else l for l in examples["label"]]
        return {"image": images, "label": labels}

    def preprocess_val(examples):
        images = [val_transforms(image.convert("RGB")) for image in examples["image"]]
        labels = [label_map.get(l, 0) if isinstance(l, str) else l for l in examples["label"]]
        return {"image": images, "label": labels}

    train_ds.set_transform(preprocess_train)
    val_ds.set_transform(preprocess_val)

    # 2. DataLoader の設定 (バッチサイズを大きく、num_workersを最適化)
    def collate_fn(batch):
        images = torch.stack([item["image"] for item in batch])
        labels = torch.tensor([item["label"] for item in batch])
        return images, labels

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, num_workers=4, pin_memory=True, collate_fn=collate_fn)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, num_workers=4, pin_memory=True, collate_fn=collate_fn)

    # 3. モデルの定義とマルチGPU (DataParallel) の有効化
    model = PostureClassifier(num_classes=NUM_CLASSES, pretrained=True)
    if torch.cuda.device_count() > 1:
        print(f"🔥 Let's use {torch.cuda.device_count()} GPUs!")
        model = nn.DataParallel(model)
    model = model.to(device)

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=1e-6)

    # クラスの不均衡を補正する重み付きLoss
    labels = train_ds["label"]
    mapped_labels = [label_map.get(l, 0) if isinstance(l, str) else l for l in labels]
    class_counts = Counter(mapped_labels)
    class_names = sorted(list(class_counts.keys()))
    weights = [1.0 / class_counts[c] for c in class_names]
    weights_tensor = torch.tensor(weights, dtype=torch.float32).to(device)
    weights_tensor = weights_tensor / weights_tensor.sum() * len(class_names)
    criterion = nn.CrossEntropyLoss(weight=weights_tensor)

    os.makedirs(args.output_dir, exist_ok=True)
    best_val_loss = float("inf")
    best_val_acc = 0.0

    for epoch in range(args.epochs):
        model.train()
        train_loss, train_correct, train_total = 0.0, 0, 0
        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            logits = model(images)
            loss = criterion(logits, labels)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()
            train_correct += (logits.argmax(dim=1) == labels).sum().item()
            train_total += labels.size(0)
        
        scheduler.step()
        train_loss /= len(train_loader)
        train_acc = train_correct / train_total

        model.eval()
        val_loss, val_correct, val_total = 0.0, 0, 0
        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(device), labels.to(device)
                logits = model(images)
                loss = criterion(logits, labels)
                val_loss += loss.item()
                val_correct += (logits.argmax(dim=1) == labels).sum().item()
                val_total += labels.size(0)
                
        val_loss /= max(len(val_loader), 1)
        val_acc = val_correct / max(val_total, 1)

        print(f"Epoch {epoch + 1:2d}/{args.epochs} | train_loss={train_loss:.4f} acc={train_acc:.4f} | val_loss={val_loss:.4f} acc={val_acc:.4f} | lr={optimizer.param_groups[0]['lr']:.2e}")

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_val_acc = val_acc
            # DataParallelの場合は model.module.state_dict() で保存するのが安全
            state_dict = model.module.state_dict() if isinstance(model, nn.DataParallel) else model.state_dict()
            torch.save(state_dict, os.path.join(args.output_dir, "best_model.pt"))

    state_dict = model.module.state_dict() if isinstance(model, nn.DataParallel) else model.state_dict()
    torch.save(state_dict, os.path.join(args.output_dir, "final_model.pt"))
    print(f"\n🎉 Training complete! Best val_acc: {best_val_acc:.4f}")

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=str, default="/home/team-008/models/posture_v4")
    parser.add_argument("--epochs", type=int, default=30)
    # バッチサイズを大幅に引き上げ
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--lr", type=float, default=5e-4)
    return parser.parse_args()

if __name__ == "__main__":
    train(parse_args())