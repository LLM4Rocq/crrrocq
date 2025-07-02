# Model Training Guide

This documents explains how to train a model using the NeMo framework, with Qwen-2.5-Coder-32B-Instruct as the default model.

We use the same hyperparameters as the ["s1: simple test-time scaling"](https://arxiv.org/abs/2501.19393) paper.

## Prerequisites

- Install the NeMo framework and its dependencies.

- Access to sufficient GPU resources (for 32b models, 8 clusters of 4xH100 was used on our end).

## Step 1: Prepare Hugging Face Model

The first step is to obtain the base Hugging Face model checkpoint and convert it into NeMo format for training.

```console
python -m src.training.prepare
```

## Step 2: Pre-tokenize the Dataset

To avoid issue with chat template and NeMo tokenizer (wrapper around Hugging Face tokenizer), we pre-tokenize the dataset using Hugging face tokenizer.

```console
python -m src.training.datamodule
```

## Step 3: Train the Model

Adjust config/nemo.yaml and job_h100.slurm file depending on your configuration.
Train Crrrocq using the prepared dataset and configuration.

```console
sbatch job_h100.slurm
```

## Step 4: Export the Model to Hugging Face Format

Once training is complete, you can export the resulting model checkpoint back to Hugging Face format.

```console
python -m src.training.export_hf
```