import os
import json
import torch
from PIL import Image
from diffusers import StableDiffusionControlNetPipeline, ControlNetModel, UniPCMultistepScheduler
from controlnet_aux import MidasDetector

# ==========================================
# 1. 設定パラメーター
# ==========================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_IMAGE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../data/base_images"))
OUTPUT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../data/synthetic_dataset"))

NUM_VARIATIONS = 100  # 1枚の元画像から何枚の架空エンジニアを生成するか

CLASSES = {
    "01_good": "A professional Japanese engineer working with good posture, bright modern office, highly detailed, 4k",
    "02_slouch": "A tired Japanese engineer slouching over a laptop, messy dark room, glowing monitor light, exhausted, cinematic lighting",
    "03_chin_rest": "A stressed Japanese engineer resting chin on hand, looking at laptop screen, server room background, deep thought, highly detailed",
    "04_stretch": "A Japanese engineer stretching arms back, relaxing on a desk chair, taking a break, coding environment"
}
NEGATIVE_PROMPT = "worst quality, low quality, bad anatomy, bad hands, missing fingers, deformed, ugly, cropped, real person face"

# ==========================================
# 2. モデルのロード
# ==========================================
print("Loading Depth AI and ControlNet models...")
midas = MidasDetector.from_pretrained("lllyasviel/Annotators")
controlnet = ControlNetModel.from_pretrained("lllyasviel/sd-controlnet-depth", torch_dtype=torch.float16)
pipe = StableDiffusionControlNetPipeline.from_pretrained(
    "runwayml/stable-diffusion-v1-5", controlnet=controlnet, torch_dtype=torch.float16
)
pipe.scheduler = UniPCMultistepScheduler.from_config(pipe.scheduler.config)
pipe.to("cuda")

# ==========================================
# 3. データ錬成ループ
# ==========================================
os.makedirs(OUTPUT_DIR, exist_ok=True)
task_id = os.environ.get("SLURM_ARRAY_TASK_ID", "0")
metadata_file = os.path.join(OUTPUT_DIR, f"metadata_task{task_id}.jsonl")

with open(metadata_file, "w", encoding="utf-8") as f_meta:
    for class_name, prompt in CLASSES.items():
        class_dir = os.path.join(BASE_IMAGE_DIR, class_name)
        if not os.path.exists(class_dir):
            continue
            
        print(f"--- Generating for {class_name} (Task: {task_id}) ---")
        for img_name in os.listdir(class_dir):
            if not img_name.lower().endswith(('.png', '.jpg', '.jpeg')):
                continue
                
            img_path = os.path.join(class_dir, img_name)
            base_image = Image.open(img_path)
            depth_image = midas(base_image)
            
            # 🔴 修正3：複数ドット対策（split('.')をやめ、os.path.splitextを使用）
            stem = os.path.splitext(img_name)[0]
            
            for i in range(NUM_VARIATIONS):
                out_filename = f"{class_name}_{stem}_task{task_id}_var{i:03d}.png"
                out_path = os.path.join(OUTPUT_DIR, out_filename)
                
                generated_image = pipe(
                    prompt,
                    negative_prompt=NEGATIVE_PROMPT,
                    image=depth_image,
                    num_inference_steps=20,
                    guidance_scale=7.5
                ).images[0]
                
                generated_image.save(out_path)
                
                metadata = {
                    "file_name": out_filename,
                    "label": class_name,
                    "prompt": prompt
                }
                f_meta.write(json.dumps(metadata) + "\n")

print(f"✨ Task {task_id} completed! ✨")