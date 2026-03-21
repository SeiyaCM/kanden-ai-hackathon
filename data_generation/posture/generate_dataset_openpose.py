import os
import json
import random
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
OUTPUT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../../data/synthetic_dataset_v3"))
NUM_VARIATIONS = 250 # 1枚のベース画像から何枚生成するか

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
    """環境・服装・人物をランダム化し、現実のノイズを再現する"""
    ages = ["a 20-year-old", "a 35-year-old", "a 50-year-old", "a young", "a middle-aged"]
    genders = ["man", "woman", "person"]
    ethnicities = ["Japanese", "Asian", "Caucasian", "Black", "Hispanic"]
    clothing = [
        "wearing a casual t-shirt", "in a cozy hoodie", "wearing a formal suit", 
        "in a knitted sweater", "wearing a tank top", "in a flannel shirt", "wearing a sports jacket"
    ]
    backgrounds = [
        "in a bright modern office", "at a messy home desk", "in a dimly lit cybercafe", 
        "at a sunny cafe table", "in a minimalist white room", "in a messy bedroom",
        "in a dark server room lit by monitor glow", "in a library", "with a plain gray background"
    ]
    lighting = [
        "natural sunlight from window", "cinematic dramatic lighting", "soft diffused lighting", 
        "neon cyberpunk lighting", "harsh fluorescent lights", "warm desk lamp light"
    ]
    angles = ["front view", "slightly angled view", "side view", "eye level camera"]
    
    prompt = f"{random.choice(ages)} {random.choice(ethnicities)} {random.choice(genders)}, sitting, {random.choice(clothing)}, {random.choice(angles)}, {random.choice(backgrounds)}, {random.choice(lighting)}, highly detailed, 4k, realistic photography"
    negative_prompt = "bad anatomy, bad hands, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, cartoon, illustration, anime"
    return prompt, negative_prompt

def main():
    # 1. モデルのロード (A5000に最適化)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    controlnet = ControlNetModel.from_pretrained("lllyasviel/sd-controlnet-openpose", torch_dtype=torch.float16)
    pipe = StableDiffusionControlNetPipeline.from_pretrained(
        "runwayml/stable-diffusion-v1-5", controlnet=controlnet, torch_dtype=torch.float16, safety_checker=None
    ).to(device)
    pipe.scheduler = UniPCMultistepScheduler.from_config(pipe.scheduler.config)
    # pipe.enable_xformers_memory_efficient_attention() # A5000でVRAM節約・高速化
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    metadata = []
    
    # 2. ベース画像の検索
    classes = sorted(os.listdir(BASE_IMAGE_DIR))
    for class_name in classes:
        class_dir = os.path.join(BASE_IMAGE_DIR, class_name)
        if not os.path.isdir(class_dir): continue
        
        out_class_dir = os.path.join(OUTPUT_DIR, class_name)
        os.makedirs(out_class_dir, exist_ok=True)
        
        base_images = [f for f in os.listdir(class_dir) if f.endswith(('.png', '.jpg'))]
        
        for img_name in base_images:
            base_path = os.path.join(class_dir, img_name)
            skeleton_img = mediapipe_to_openpose(base_path)
            if skeleton_img is None: continue
            
            print(f"Generating variations for {class_name}/{img_name}...")
            
            for i in tqdm(range(NUM_VARIATIONS)):
                prompt, neg_prompt = generate_random_prompt()
                
                # 画像生成
                generated = pipe(
                    prompt, negative_prompt=neg_prompt, image=skeleton_img,
                    num_inference_steps=20, guidance_scale=7.5
                ).images[0]
                
                out_name = f"{class_name}_{os.path.splitext(img_name)[0]}_var{i:03d}.png"
                out_path = os.path.join(out_class_dir, out_name)
                generated.save(out_path)
                
                metadata.append({
                    "file_name": os.path.join(class_name, out_name),
                    "label": class_name,
                    "prompt": prompt
                })

    # 3. メタデータの保存
    with open(os.path.join(OUTPUT_DIR, "metadata.jsonl"), "w") as f:
        for item in metadata:
            f.write(json.dumps(item) + "\n")
    print(f"Generation complete. Saved to {OUTPUT_DIR}")

if __name__ == "__main__":
    main()