"""
Code from https://github.com/NVIDIA/NeMo/blob/main/tutorials/llm/distill_deepseek_r1/qwen2_distill_nemo.ipynb
"""
import argparse

import yaml
import nemo_run as run
import pytorch_lightning as pl
from nemo.collections import llm

parser = argparse.ArgumentParser()
parser.add_argument("--config-file", type=str, help="configuration file for training")
args = parser.parse_args()

with open(args.config_file, 'r') as file:
    config_file = yaml.safe_load(file)

# We use run.Partial to configure this function
def configure_checkpoint_conversion(model_name):
    return run.Partial(
        llm.import_ckpt,
        model=llm.qwen25_32b.model(),
        source=f"hf://{model_name}",
        overwrite=True,
    )

# configure your function
import_ckpt = configure_checkpoint_conversion(config_file['model_name'])
# define your executor
local_executor = run.LocalExecutor()

# run your experiment
run.run(import_ckpt, executor=local_executor)