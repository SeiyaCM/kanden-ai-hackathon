"""Configuration for SO-ARM101 robot arm candy delivery."""

import os

# Robot hardware
ROBOT_TYPE = os.getenv("ROBOT_TYPE", "so100")

# ACT policy checkpoint path
ACT_CHECKPOINT_PATH = os.getenv(
    "ACT_CHECKPOINT_PATH",
    "outputs/act_candy_basket/checkpoints/last/pretrained_model",
)

# Control parameters
CONTROL_FPS = int(os.getenv("CONTROL_FPS", "30"))
