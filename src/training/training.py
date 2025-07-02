"""
Code from https://github.com/NVIDIA/NeMo/blob/main/tutorials/llm/distill_deepseek_r1/qwen2_distill_nemo.ipynb
"""

from pathlib import Path
import argparse
import yaml

import fiddle as fdl

import nemo_run as run
from nemo import lightning as nl
from nemo.collections import llm
from nemo.collections.llm.recipes.precision.mixed_precision import bf16_mixed
from megatron.core.optimizer import OptimizerConfig

import pytorch_lightning as pl

from .datamodule import crrrocq

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-file", type=str, help="configuration file for training")
    args = parser.parse_args()
    return args

# Configure the trainer
def trainer(config_strategy, config_trainer, num_nodes:int=1) -> run.Config[nl.Trainer]:
    strategy = run.Config(
        nl.MegatronStrategy,
        **config_strategy
    )
    trainer = run.Config(
        nl.Trainer,
        num_nodes=num_nodes,
        plugins=bf16_mixed(),
        strategy=strategy,
        **config_trainer
    )
    return trainer


# Configure the logger
def logger(**kwargs) -> run.Config[nl.NeMoLogger]:
    ckpt = run.Config(
        nl.ModelCheckpoint,
        **kwargs
    )

    return run.Config(
        nl.NeMoLogger,
        name="qwen_sft",
        log_dir="./results",
        use_datetime_version=False,
        ckpt=ckpt,
        wandb=None
    )


# Configure the optimizer
def adam_with_cosine_annealing(config_optimizer, config_scheduler) -> run.Config[nl.OptimizerModule]:
    opt_cfg = run.Config(
        OptimizerConfig,
        **config_optimizer
    )
    scheduler = run.Config(
        nl.lr_scheduler.CosineAnnealingScheduler,
        **config_scheduler
    )
    return run.Config(
        nl.MegatronOptimizerModule,
        lr_scheduler=scheduler,
        config=opt_cfg
    )

map_str_config = {
    "Qwen25Config1P5B": llm.Qwen25Config1P5B,
    "Qwen25Config7B": llm.Qwen25Config7B,
    "Qwen25Config14B": llm.Qwen25Config14B,
    "Qwen25Config32B": llm.Qwen25Config32B,
    "Qwen25Config72B": llm.Qwen25Config72B,
    "Qwen25Config500M": llm.Qwen25Config500M,
}
# Configure the model
# We use Qwen2Config7B to configure the model.
def qwen(model_config) -> run.Config[pl.LightningModule]:
    return run.Config(llm.Qwen2Model, config=run.Config(map_str_config[model_config]))

# Configure the resume
def resume(model_name) -> run.Config[nl.AutoResume]:
    return run.Config(
        nl.AutoResume,
        restore_config=run.Config(nl.RestoreConfig,
            path=f"nemo://{model_name}"
        ),
        resume_if_exists=True,
    )

def configure_finetuning_recipe(config):
    model_name = config['model_name']
    model_config = config['model_config']
    config_trainer = config['trainer']
    config_strategy = config['strategy']
    config_datamodule = config['datamodule']
    config_logger = config['logger']
    config_optim = config['optimizer']
    config_scheduler = config['scheduler']
    return run.Partial(
        llm.finetune,
        model=qwen(model_config),
        trainer=trainer(config_strategy, config_trainer, num_nodes=config['nodes']),
        data=crrrocq(model_name, **config_datamodule),
        log=logger(**config_logger),
        optim=adam_with_cosine_annealing(config_optim, config_scheduler),
        resume=resume(model_name),
    )

def local_executor_torchrun(ntasks_per_node: int = 1) -> run.LocalExecutor:
    # Env vars for jobs are configured here
    env_vars = {
        "TORCH_NCCL_AVOID_RECORD_STREAMS": "1",
        "NCCL_NVLS_ENABLE": "0",
        "NVTE_DP_AMAX_REDUCE_INTERVAL": "0",
        "NVTE_ASYNC_AMAX_REDUCTION": "1",
    }

    executor = run.LocalExecutor(ntasks_per_node=ntasks_per_node, launcher="torchrun", env_vars=env_vars)

    return executor


if __name__ == '__main__':

    args = parse_args()
    with open(args.config_file, 'r') as file:
        config_file = yaml.safe_load(file)
    
    ntasks_per_node = config_file['ntasks_per_node']
    gpus = config_file['gpus_per_node']
    nodes = config_file['nodes']
    recipe = configure_finetuning_recipe(config_file)
    recipe_obj = fdl.build(recipe)
    recipe_obj()