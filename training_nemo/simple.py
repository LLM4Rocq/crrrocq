

from functools import partial

import fiddle as fdl
import lightning.pytorch as pl
from lightning.pytorch.loggers import WandbLogger
from torch.utils.data import DataLoader

from nemo import lightning as nl
from nemo.collections import llm
from nemo.lightning.pytorch.callbacks import JitConfig, JitTransform

class SquadDataModuleWithPthDataloader(llm.SquadDataModule):
    """Creates a squad dataset with a PT dataloader"""

    def _create_dataloader(self, dataset, mode, **kwargs) -> DataLoader:
        return DataLoader(
            dataset,
            num_workers=self.num_workers,
            pin_memory=self.pin_memory,
            persistent_workers=self.persistent_workers,
            collate_fn=dataset.collate_fn,
            batch_size=self.micro_batch_size,
            **kwargs,
        )


def squad(tokenizer, mbs=1, gbs=2) -> pl.LightningDataModule:
    """Instantiates a SquadDataModuleWithPthDataloader and return it

    Args:
        tokenizer (AutoTokenizer): the tokenizer to use

    Returns:
        pl.LightningDataModule: the dataset to train with.
    """
    return SquadDataModuleWithPthDataloader(
        tokenizer=tokenizer,
        seq_length=512,
        micro_batch_size=mbs,
        global_batch_size=gbs,
        num_workers=0,
        dataset_kwargs={
            "sanity_check_dist_workers": False,
            "get_attention_mask_from_fusion": True,
        },
    )



# In order to use the models like Llama, Gemma, you need to ask for permission on the HF model page and then pass the HF_TOKEN in the next cell.
# model_name = "google/gemma-2b" # HF model name. This can be the path of the downloaded model as well.
model_name = "meta-llama/Llama-3.2-1B"  # HF model name. This can be the path of the downloaded model as well.
strategy = "ddp" # Distributed training strategy such as DDP, FSDP2, etc.
max_steps = 100 # Number of steps in the training loop.
accelerator = "gpu"
num_devices = 2  # Number of GPUs to run this notebook on.
wandb_name = None  # name of the wandb experiment.
use_torch_jit = False # torch jit can be enabled.
ckpt_folder="/opt/checkpoints/automodel_experiments/"



import os
os.environ["HF_TOKEN"] ='<HF_TOKEN>'




def make_strategy(strategy, model, devices, num_nodes, adapter_only=False):
    """
    Creates and returns a distributed training strategy based on the provided strategy type.

    Parameters:
        strategy (str): The name of the strategy ('ddp', 'fsdp2', or other).
        model: The model instance, which provides a method to create the HF checkpoint IO.
        devices (int): Number of devices per node.
        num_nodes (int): Number of compute nodes.
        adapter_only (bool, optional): Whether to save only adapter-related parameters in the checkpoint. Default is False.

    Returns:
        A PyTorch Lightning or custom distributed training strategy.
    """

    if strategy == 'ddp':  # Distributed Data Parallel (DDP) strategy
        return pl.strategies.DDPStrategy(
            checkpoint_io=model.make_checkpoint_io(adapter_only=adapter_only),
        )

    elif strategy == 'fsdp2':  # Fully Sharded Data Parallel (FSDP) v2 strategy
        return nl.FSDP2Strategy(
            data_parallel_size=devices * num_nodes,  # Defines total data parallel size
            tensor_parallel_size=1,  # No tensor parallelism
            checkpoint_io=model.make_checkpoint_io(adapter_only=adapter_only),
        )

    else:  # Default to single device strategy (useful for debugging or single-GPU training)
        return pl.strategies.SingleDeviceStrategy(
            device='cuda:0',  # Uses the first available CUDA device
            checkpoint_io=model.make_checkpoint_io(adapter_only=adapter_only),
        )

wandb = WandbLogger(
    project="nemo_automodel",
    name=wandb_name,
) if wandb_name is not None else None

callbacks = []
if use_torch_jit:
    jit_config = JitConfig(use_torch=True, torch_kwargs={'dynamic': False}, use_thunder=False)
    callbacks = [JitTransform(jit_config)]

callbacks.append(
    nl.ModelCheckpoint(
        every_n_train_steps=max_steps // 2,
        dirpath=ckpt_folder,
    )
)

model = llm.HFAutoModelForCausalLM(model_name=model_name)

# Create model strategy
strategy = make_strategy(strategy, model, num_devices, 1)

trainer = nl.Trainer(
    devices=num_devices,
    max_steps=max_steps,
    accelerator="gpu",
    strategy=strategy,
    log_every_n_steps=1,
    limit_val_batches=0.0,
    num_sanity_val_steps=0,
    accumulate_grad_batches=1,
    gradient_clip_val=1.0,
    use_distributed_sampler=False,
    logger=wandb,
    callbacks=callbacks,
    precision="bf16",
)

llm.api.finetune(
    model=model,
    data=squad(llm.HFAutoModelForCausalLM.configure_tokenizer(model_name), gbs=1),
    trainer=trainer,
    optim=fdl.build(llm.adam.pytorch_adam_with_flat_lr(lr=1e-5)),
    peft=None,
    log=None,
)

