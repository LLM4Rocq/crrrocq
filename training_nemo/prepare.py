"""
Code from https://github.com/NVIDIA/NeMo/blob/main/tutorials/llm/distill_deepseek_r1/qwen2_distill_nemo.ipynb
"""

import nemo_run as run
import pytorch_lightning as pl
from nemo.collections import llm

# llm.import_ckpt is the nemo2 API for converting Hugging Face checkpoint to NeMo format
# example python usage:
# llm.import_ckpt(model=llm.llama3_8b.model(), source="hf://meta-llama/Meta-Llama-3-8B")
#
# We use run.Partial to configure this function
def configure_checkpoint_conversion():
    return run.Partial(
        llm.import_ckpt,
        model=llm.qwen2_32b.model(),
        source="hf://Qwen/Qwen2.5-32B-Instruct",
        overwrite=True,
    )

# configure your function
import_ckpt = configure_checkpoint_conversion()
# define your executor
local_executor = run.LocalExecutor()

# run your experiment
run.run(import_ckpt, executor=local_executor)