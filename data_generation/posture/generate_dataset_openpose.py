import os
import json
import random
import argparse
import torch
import cv2
import numpy as np
import mediapipe as mp
from PIL import Image
from diffusers import StableDiffusionControlNetPipeline, ControlNetModel, UniPCMultistepScheduler
from tqdm import tqdm

# --- 設定パラメータ ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_IMAGE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../../data/base_images"))
OUTPUT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../../data/synthetic_dataset_v4"))
NUM_VARIATIONS = 2500  # 1枚のベース画像から何枚生成するか
BATCH_SIZE = 4  # A5000 (24GB VRAM) で同時生成する枚数

# --- MediaPipe 初期化 ---
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(static_image_mode=True, min_detection_confidence=0.5)

# --- OpenPose 描画用設定 ---
COLORS = [
    (0, 0, 255), (0, 85, 255), (0, 170, 255), (0, 255, 255), (0, 255, 170), (0, 255, 85), 
    (0, 255, 0), (85, 255, 0), (170, 255, 0), (255, 255, 0), (255, 170, 0), (255, 85, 0), 
    (255, 0, 0), (255, 0, 85), (255, 0, 170), (255, 0, 255), (170, 0, 255), (85, 0, 255)
]
PAIRS = [
    (1, 2), (1, 5), (2, 3), (3, 4), (5, 6), (6, 7), (1, 8), (8, 9), (9, 10), 
    (1, 11), (11, 12), (12, 13), (1, 0), (0, 14), (14, 16), (0, 15), (15, 17)
]

def mediapipe_to_openpose(img_path):
    img = cv2.imread(img_path)
    if img is None: return None
    h, w, _ = img.shape
    results = pose.process(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    
    canvas = np.zeros((h, w, 3), dtype=np.uint8)
    if not results.pose_landmarks: return None

    lm = results.pose_landmarks.landmark
    openpose_pts = {
        0: (lm[0].x, lm[0].y), 1: ((lm[11].x + lm[12].x)/2, (lm[11].y + lm[12].y)/2),
        2: (lm[12].x, lm[12].y), 3: (lm[14].x, lm[14].y), 4: (lm[16].x, lm[16].y),
        5: (lm[11].x, lm[11].y), 6: (lm[13].x, lm[13].y), 7: (lm[15].x, lm[15].y),
        14: (lm[5].x, lm[5].y), 15: (lm[2].x, lm[2].y), 16: (lm[8].x, lm[8].y), 17: (lm[7].x, lm[7].y),
    }

    pts = {i: (int(pt[0]*w), int(pt[1]*h)) for i, pt in openpose_pts.items() if 0 <= pt[0] < 1 and 0 <= pt[1] < 1}
    for i, pair in enumerate(PAIRS):
        if pair[0] in pts and pair[1] in pts:
            cv2.line(canvas, pts[pair[0]], pts[pair[1]], COLORS[i], thickness=4)
    for i in range(18):
        if i in pts: cv2.circle(canvas, pts[i], radius=4, color=COLORS[i], thickness=-1)

    return Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB))

def generate_random_prompt():
    """環境・服装・人物をランダム化し、Webカメラ特有の悪条件を再現する"""
    ages = ["a 20-year-old", "a 35-year-old", "a 50-year-old", "a young", "a middle-aged"]
    genders = ["man", "woman", "person"]
    ethnicities = ["Japanese", "Asian", "Caucasian", "Black", "Hispanic"]
    clothing = [
        "wearing a casual t-shirt", "in a cozy hoodie", "wearing a formal suit",
        "in a knitted sweater", "wearing a tank top", "in a flannel shirt", "wearing a sports jacket",
        "wearing dark black clothes", "in dark navy shirt blending with background",
    ]
    accessories = ["wearing glasses", "wearing a face mask", "wearing a hat", "wearing earphones"]
    backgrounds = [
        "in a bright modern office", "at a messy home desk", "in a dimly lit cybercafe",
        "at a sunny cafe table", "in a minimalist white room", "in a messy bedroom",
        "in a dark server room lit by monitor glow", "in a library", "with a plain gray background",
        "messy office background", "cluttered room", "small cramped apartment",
        "busy coworking space with people behind",
    ]
    lighting = [
        "natural sunlight from window", "cinematic dramatic lighting", "soft diffused lighting",
        "neon cyberpunk lighting", "harsh fluorescent lights", "warm desk lamp light",
        "dimly lit room", "low light environment", "fluorescent lighting",
        "screen glow only", "harsh overhead light", "backlit by window",
    ]
    angles = [
        "front view", "slightly angled view", "side view", "eye level camera",
        "webcam point of view", "low angle shot", "high angle shot",
        "shot from below", "shot from above", "overhead webcam view", "laptop webcam angle",
    ]
    noise_effects = [
        "motion blur", "webcam artifact", "grainy",
        "slightly out of focus", "low resolution webcam quality",
    ]

    prompt = f"{random.choice(ages)} {random.choice(ethnicities)} {random.choice(genders)}, sitting, {random.choice(clothing)}, {random.choice(angles)}, {random.choice(backgrounds)}, {random.choice(lighting)}, highly detailed, realistic photography"

    # 30%の確率でアクセサリーを1〜2個独立付与
    if random.random() < 0.3:
        chosen_acc = random.sample(accessories, random.randint(1, 2))
        prompt += ", " + ", ".join(chosen_acc)

    # ランダムに0〜2個の画質ノイズを付与
    num_noise = random.randint(0, 2)
    if num_noise > 0:
        chosen_noise = random.sample(noise_effects, num_noise)
        prompt += ", " + ", ".join(chosen_noise)

    negative_prompt = "bad anatomy, bad hands, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, cartoon, illustration, anime"
    return prompt, negative_prompt

def parse_args():
    parser = argparse.ArgumentParser(description="悪条件データ生成 (v4)")
    parser.add_argument("--class-name", type=str, default=None,
                        help="対象クラス名 (例: 01_good)。未指定時は全クラス処理")
    parser.add_argument("--num-variations", type=int, default=NUM_VARIATIONS,
                        help="1枚のベース画像あたりの生成枚数")
    return parser.parse_args()


def main():
    args = parse_args()
    num_variations = args.num_variations

    # 1. モデルのロード (A5000に最適化)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    controlnet = ControlNetModel.from_pretrained("lllyasviel/sd-controlnet-openpose", torch_dtype=torch.float16)
    pipe = StableDiffusionControlNetPipeline.from_pretrained(
        "runwayml/stable-diffusion-v1-5", controlnet=controlnet, torch_dtype=torch.float16, safety_checker=None
    ).to(device)
    pipe.scheduler = UniPCMultistepScheduler.from_config(pipe.scheduler.config)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 2. メタデータファイルを追記モードで開く（クラッシュ耐性）
    meta_filename = f"metadata_{args.class_name}.jsonl" if args.class_name else "metadata.jsonl"
    meta_path = os.path.join(OUTPUT_DIR, meta_filename)
    generated_count = 0

    # 3. ベース画像の検索
    if args.class_name:
        classes = [args.class_name]
    else:
        classes = sorted(os.listdir(BASE_IMAGE_DIR))

    with open(meta_path, "a") as f_meta:
        for class_name in classes:
            class_dir = os.path.join(BASE_IMAGE_DIR, class_name)
            if not os.path.isdir(class_dir):
                continue

            out_class_dir = os.path.join(OUTPUT_DIR, class_name)
            os.makedirs(out_class_dir, exist_ok=True)

            base_images = [f for f in os.listdir(class_dir) if f.endswith(('.png', '.jpg'))]

            for img_name in base_images:
                base_path = os.path.join(class_dir, img_name)
                skeleton_img = mediapipe_to_openpose(base_path)
                if skeleton_img is None:
                    continue

                print(f"Generating {num_variations} variations for {class_name}/{img_name}...")

                for i in tqdm(range(0, num_variations, BATCH_SIZE)):
                    current_batch = min(BATCH_SIZE, num_variations - i)
                    prompts, neg_prompts = zip(*[generate_random_prompt() for _ in range(current_batch)])

                    # バッチ生成（A5000 VRAM活用）
                    images = pipe(
                        list(prompts), negative_prompt=list(neg_prompts),
                        image=[skeleton_img] * current_batch,
                        num_inference_steps=20, guidance_scale=7.5,
                    ).images

                    for j, generated in enumerate(images):
                        idx = i + j
                        out_name = f"{class_name}_{os.path.splitext(img_name)[0]}_var{idx:04d}.png"
                        out_path = os.path.join(out_class_dir, out_name)
                        generated.save(out_path)

                        f_meta.write(json.dumps({
                            "file_name": os.path.join(class_name, out_name),
                            "label": class_name,
                            "prompt": prompts[j],
                        }) + "\n")
                        f_meta.flush()
                        generated_count += 1

    print(f"Generation complete. {generated_count} images saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()