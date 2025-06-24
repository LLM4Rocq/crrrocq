"""
Code from https://github.com/NVIDIA/NeMo/blob/main/tutorials/llm/distill_deepseek_r1/qwen2_distill_nemo.ipynb
"""

from pathlib import Path

import nemo_run as run
import pytorch_lightning as pl
from nemo.collections import llm

sft_ckpt_path=str(next((d for d in Path("./results/qwen_sft/checkpoints/").iterdir() if d.is_dir() and d.name.endswith("-last")), None))

print("We will load SFT checkpoint from:", sft_ckpt_path)

# llm.export_ckpt is the nemo2 API for exporting a NeMo checkpoint to Hugging Face format
# example python usage:
# llm.export_ckpt(path="/path/to/model.nemo", target="hf", output_path="/path/to/save")
def configure_checkpoint_conversion():
    return run.Partial(
        llm.export_ckpt,
        path=sft_ckpt_path,
        target="hf",
        output_path="./model"
    )

# configure your function
export_ckpt = configure_checkpoint_conversion()
# define your executor
local_executor = run.LocalExecutor()

# run your experiment
run.run(export_ckpt, executor=local_executor)