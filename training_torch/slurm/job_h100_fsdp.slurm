#!/bin/bash

#SBATCH --job-name=crrrocq # job's name
#SBATCH --output=crrrocq%j.out # output log (%j = job ID)
#SBATCH --error=crrrocq%j.err # error log (%j = job ID)
#SBATCH --constraint=h100 # h100 gpus
#SBATCH --nodes=4 # number of nodes
#SBATCH --ntasks-per-node=1 # beware, idr_accelerate manage subtasks, don't change this parameter
#SBATCH --gres=gpu:4 # number of gpus/node
#SBATCH --cpus-per-task=96 # cpus/per_tasks
#SBATCH --time=01:50:00 # maximal duration "(HH:MM:SS)"
#SBATCH --qos=qos_gpu_h100-dev # QoS
#SBATCH --hint=nomultithread # no hyperthreading
#SBATCH --account=isf@h100 # account

module purge
conda deactivate

module load arch/h100
module load pytorch-gpu/py3/2.6.0
export SCRATCH="/lustre/fsn1/projects/rech/isf/ulu88xb"
export USE_FLASH_ATTENTION=1
set -x
cd $SCRATCH/crrrocq

export NCCL_DEBUG=INFO
export NCCL_TIMEOUT=3600
export HF_DATASETS_CACHE="$SCRATCH/HF/datasets_cache"
export HF_HOME="$SCRATCH/HF"
export MLFLOW_TRACKING_URI="$SCRATCH/HF/mlruns"


srun idr_accelerate --config_file training/config/fsdp_config_scratch.yaml --mixed-precision bf16 -m training.training_scratch \
    --model-name="$SCRATCH/models/Qwen-32B" --batch-size 1 --empty-cache true
