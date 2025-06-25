"""
Readaptation from https://github.com/NVIDIA/NeMo/blob/main/tutorials/llm/distill_deepseek_r1/qwen2_distill_nemo.ipynb
"""

import json
import shutil
from typing import TYPE_CHECKING, Any, Dict, List, Optional

# import numpy as np
from datasets import load_dataset
from nemo.collections.common.tokenizers.huggingface.auto_tokenizer import AutoTokenizer

from nemo.collections.llm.gpt.data.core import get_dataset_root
from nemo.collections.llm.gpt.data.fine_tuning import FineTuningDataModule
from nemo.lightning.io.mixin import IOMixin
from nemo.utils import logging

import nemo_run as run
import pytorch_lightning as pl

from functools import lru_cache

from nemo.collections.llm.gpt.data.core import create_sft_dataset

if TYPE_CHECKING:
    from nemo.collections.common.tokenizers import TokenizerSpec
    from nemo.collections.llm.gpt.data.packed_sequence import PackedSequenceSpecs

from training_nemo.dataset import GPTSFTDatasetInterleaved

class CrrrocqDataModule(FineTuningDataModule, IOMixin):
    """A data module for fine-tuning on the Crrrocq dataset.

    Args:
        See FineTuningDataModule for the args
    """

    def __init__(
        self,
        seq_length: int = 2048,
        tokenizer: Optional["TokenizerSpec"] = None,
        micro_batch_size: int = 4,
        global_batch_size: int = 8,
        rampup_batch_size: Optional[List[int]] = None,
        seed: int = 1234,
        memmap_workers: int = 1,
        num_workers: int = 8,
        pin_memory: bool = True,
        persistent_workers: bool = False,
        packed_sequence_specs: Optional["PackedSequenceSpecs"] = None,
        dataset_kwargs: Optional[Dict[str, Any]] = None,
        dataset_root: str = "crrrocq_ds",
        dataset_raw_filepath: str = "export/dataset/train.json",
        prompt_filepath: str = "export/dataset/prompt.json"
    ):
        self.dataset_raw_filepath = dataset_raw_filepath
        self.prompt_filepath = prompt_filepath
        self.output_jsonl = {}
        super().__init__(
            dataset_root=dataset_root,
            seq_length=seq_length,
            tokenizer=tokenizer,
            micro_batch_size=micro_batch_size,
            global_batch_size=global_batch_size,
            rampup_batch_size=rampup_batch_size,
            seed=seed,
            memmap_workers=memmap_workers,
            num_workers=num_workers,
            pin_memory=pin_memory,
            persistent_workers=persistent_workers,
            packed_sequence_specs=packed_sequence_specs,
            dataset_kwargs=dataset_kwargs,
        )

    def prepare_data(self) -> None:
        # if train file is specified, no need to do anything
        self._preprocess_and_split_data(self.dataset_raw_filepath)
        super().prepare_data()


    def _preprocess_and_split_data(self, dset, train_ratio: float = 0.80, val_ratio: float = 0.15):
        logging.info(f"Preprocessing {self.__class__.__name__} to jsonl format and splitting...")

        test_ratio = 1 - train_ratio - val_ratio
        save_splits = {}
        dset = load_dataset(
            "json",
            data_files={
                "train": self.dataset_raw_filepath
            }
        )
        dataset = dset.get('train')
        split_dataset = dataset.train_test_split(test_size=val_ratio + test_ratio, seed=self.seed)
        split_dataset2 = split_dataset['test'].train_test_split(
            test_size=test_ratio / (val_ratio + test_ratio), seed=self.seed
        )
        save_splits['training'] = split_dataset['train']
        save_splits['validation'] = split_dataset2['train']
        save_splits['test'] = split_dataset2['test']

        print("len training: ", len(save_splits['training']))
        print("len validation: ", len(save_splits['validation']))
        print("len test: ", len(save_splits['test']))

        for split_name, dataset in save_splits.items():
            output_file = self.dataset_root / f"{split_name}.jsonl"
            with output_file.open("w", encoding="utf-8") as f:
                for example in dataset:                   
                    f.write(json.dumps(example) + "\n")

            logging.info(f"{split_name} split saved to {output_file}")
            self.output_jsonl[split_name]=output_file


    @lru_cache
    def _create_dataset(self, is_test=False, pack_metadata_file_path = None, **kwargs):
        # pylint: disable=C0115,C0116
        return GPTSFTDatasetInterleaved(
            file_path=self.dataset_root / "training.jsonl", #self.output_jsonl['training'],
            prompt_path=self.prompt_filepath,
            tokenizer=self.tokenizer,
            max_seq_length=self.seq_length,
            seed=self.seed,
            is_test=is_test,
            memmap_workers=self.memmap_workers,
        )

def crrrocq(model_name, **kwargs) -> run.Config[pl.LightningDataModule]:
    tokenizer = AutoTokenizer(model_name)
    return run.Config(CrrrocqDataModule, tokenizer=tokenizer, **kwargs)


if __name__ == '__main__':
    from transformers import AutoTokenizer
    import torch
    model_name = "Qwen/Qwen2.5-32B-Instruct"
    tokenizer = AutoTokenizer(model_name)

    dm = CrrrocqDataModule(tokenizer=tokenizer)
    dm.prepare_data()
    ds = dm._create_dataset()
    for entry in ds:
        input_ids = torch.tensor(entry['input_ids'])
        ignore_idx = torch.tensor(entry['ignore_idx'])

        input_ids = input_ids.where(ignore_idx==1, 0)
        print(tokenizer.tokenizer.decode(input_ids))
        input('Continue?')