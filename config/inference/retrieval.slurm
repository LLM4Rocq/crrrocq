#!/bin/bash
#SBATCH --job-name=retrieval
#SBATCH --output=SLURM_Logs/retrieval%j.out
#SBATCH --error=SLURM_Logs/retrieval%j.err
#SBATCH --nodes=1
#SBATCH --cpus-per-task=16
#SBATCH --ntasks-per-node=1
#SBATCH --partition=cpu_p1
#SBATCH --account=tdm@cpu
#SBATCH --qos=qos_cpu-dev
#SBATCH --hint=nomultithread
#SBATCH --time=02:00:00

module purge
conda deactivate
cd $SCRATCH/crrrocq

source /lustre/fswork/projects/rech/tdm/commun/venv/crrrocq/bin/activate

HEAD_NODE=$(scontrol show hostname "$SLURM_NODELIST" | head -n 1)

# srun --export=ALL bash -lc '
#   source /lustre/fswork/projects/rech/tdm/commun/venv/crrrocq/bin/activate
# ' &
# 
# sleep 60

echo $HEAD_NODE > /lustre/fsn1/projects/rech/tdm/commun/retrieval_ip.txt

gunicorn -w 8 -b 0.0.0.0:5001 src.servers.retrieval.app:app

wait