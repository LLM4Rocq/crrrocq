#!/bin/bash

#SBATCH --job-name=Babel-formal # nom du job
#SBATCH --output=babel%j.out # fichier de sortie (%j = job ID)
#SBATCH --error=babel%j.err # fichier d’erreur (%j = job ID)
#SBATCH --constraint=a100 # demander des GPU a 16 Go de RAM
#SBATCH --nodes=2 # reserver 1 nœud
#SBATCH --ntasks-per-node=8 # reserver 8 taches (ou processus)
#SBATCH --gres=gpu:8 # reserver 8 GPU
#SBATCH --cpus-per-task=8 # reserver 4 CPU par tache (et memoire associee)
#SBATCH --time=06:00:00 # temps maximal d’allocation "(HH:MM:SS)"
#SBATCH --qos=qos_gpu_a100-t3 # QoS
#SBATCH --hint=nomultithread # desactiver l’hyperthreading
#SBATCH --account=mmr@a100 # comptabilite V100

module purge # nettoyer les modules herites par defaut
conda deactivate # desactiver les environnements herites par defaut

module load arch/h100
module load pytorch-gpu/py3/2.6.0 # charger les modules
# set -x # activer l’echo des commandes
cd $SCRATCH/babel
export SCRATCH="/lustre/fsn1/projects/rech/mmr/ulu88xb"
export NCCL_DEBUG=INFO
export NCCL_TIMEOUT=3600
export OMP_NUM_THREADS=8
export HF_DATASETS_CACHE="$SCRATCH/HF/datasets_cache"
export HF_HOME="$SCRATCH/HF/transformers_cache"
export MLFLOW_TRACKING_URI="$SCRATCH/HF/mlruns"
export node_array=$(scontrol show hostnames $SLURM_JOB_NODELIST)
export nnodes=$(echo $node_array | wc -w)
export head_node=($node_array)
export head_node_ip=$(ssh -y $head_node hostname --ip-address)

srun python -m torch.distributed.run --nproc-per-node 1 \
    --nnodes=2 \
    --rdzv_id="babel-formal" \
    --rdzv_backend=c10d \
    --rdzv_endpoint=172.20.5.17:19250 \
    src/training/training.py \
    --block_size=10000 \
    --per_device_train_batch_size=1 \
    --per_device_eval_batch_size=1 \
    --gradient_accumulation_steps=1 \
    --num_train_epochs=5 \
    --model_name="$SCRATCH/models/Qwen-1.5B" \
    --warmup_ratio=0.05 \
    --fsdp="full_shard auto_wrap" \
    --fsdp_config="src/training/config/fsdp_config_qwen.json" \
    --bf16=True \
    --eval_strategy="no" \
    --logging_steps=1 \
    --lr_scheduler_type="cosine" \
    --learning_rate=1e-5 \
    --weight_decay=1e-4 \
    --adam_beta1=0.9 \
    --adam_beta2=0.95 \
    --output_dir="$SCRATCH/training/ckpts/" \
    --save_only_model=True \
    --gradient_checkpointing=True \
    --save-steps=75 \
    --logging_dir="$SCRATCH/training/runs" \
    --report_to="tensorboard" \
    --logging_steps=1
