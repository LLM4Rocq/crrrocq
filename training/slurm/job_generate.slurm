#!/bin/bash

#SBATCH --job-name=Babel-formal # job's name
#SBATCH --output=babel%j.out # output log (%j = job ID)
#SBATCH --error=babel%j.err # error log (%j = job ID)
#SBATCH --constraint=h100 # h100 gpus
#SBATCH --nodes=1 # number of nodes
#SBATCH --ntasks-per-node=1 # beware, idr_accelerate manage subtasks, don't change this parameter
#SBATCH --gres=gpu:4 # number of gpus/node
#SBATCH --cpus-per-task=96 # cpus/per_tasks
#SBATCH --time=13:00:00 # maximal duration "(HH:MM:SS)"
#SBATCH --qos=qos_gpu_h100-t3 # QoS
#SBATCH --hint=nomultithread # no hyperthreading
#SBATCH --account=mmr@h100 # account


module purge
conda deactivate

module load arch/h100
module load pytorch-gpu/py3/2.5.0
export SCRATCH="/lustre/fsn1/projects/rech/mmr/ulu88xb"

cd $SCRATCH/babel

export NCCL_DEBUG=INFO
export NCCL_TIMEOUT=3600
export HF_DATASETS_CACHE="$SCRATCH/HF/datasets_cache"
export HF_HOME="$SCRATCH/HF/transformers_cache"
export MLFLOW_TRACKING_URI="$SCRATCH/HF/mlruns"

srun python -m src.training.generate_local
