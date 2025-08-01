#!/bin/bash

#SBATCH --job-name=crrrocq # job's name
#SBATCH --output=crrrocq%j.out # output log (%j = job ID)
#SBATCH --error=crrrocq%j.err # error log (%j = job ID)
#SBATCH --constraint=h100 # h100 gpus
#SBATCH --nodes=8 # number of nodes
#SBATCH --ntasks-per-node=1 # beware, idr_accelerate manage subtasks, don't change this parameter
#SBATCH --gres=gpu:4 # number of gpus/node
#SBATCH --cpus-per-task=96 # cpus/per_tasks
#SBATCH --time=06:30:00 # maximal duration "(HH:MM:SS)"
#SBATCH --qos=qos_gpu_h100-t3 # QoS
#SBATCH --hint=nomultithread # no hyperthreading
#SBATCH --account=tdm@h100 # account

module purge
conda deactivate

module load arch/h100
module load miniforge cuda/12.4.1 cudnn/9.7.1.26-cuda nccl/2.25.1-1-cuda

conda activate nemo

export SCRATCH="/lustre/fsn1/projects/rech/tdm/ulu88xb"
export HF_HOME="$SCRATCH/HF"

set -x
cd $SCRATCH/crrrocq

head_node=$(scontrol show hostnames $SLURM_JOB_NODELIST | head -n 1)

srun torchrun \
            --nproc-per-node=4 \
            --nnodes=${SLURM_NNODES} \
            --rdzv-backend=c10d \
            --rdzv-endpoint=${head_node}:29500 \
            --rdzv-id=abc123 \
            -m src.training.training --config-file "config/training/nemo.yaml"
