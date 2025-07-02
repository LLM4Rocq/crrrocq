"""
Code from https://github.com/NVIDIA/NeMo/blob/main/tutorials/llm/distill_deepseek_r1/qwen2_distill_nemo.ipynb
"""

from pathlib import Path
import argparse
import yaml

import nemo_run as run
import pytorch_lightning as pl
from nemo.collections import llm

parser = argparse.ArgumentParser()
parser.add_argument("--ckpt-path", type=str, default="results/qwen_sft/checkpoints/")
args = parser.parse_args()

sft_ckpt_path=str(next((d for d in Path(args.ckpt_path).iterdir() if d.is_dir() and d.name.endswith("-last")), None))

print("We will load SFT checkpoint from:", sft_ckpt_path)

def configure_checkpoint_conversion():
    return run.Partial(
        llm.export_ckpt,
        path=sft_ckpt_path,
        target="hf",
        output_path="model/"
    )

# configure your function
export_ckpt = configure_checkpoint_conversion()
# define your executor
local_executor = run.LocalExecutor()

# run your experiment
run.run(export_ckpt, executor=local_executor)