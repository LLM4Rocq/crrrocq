#!/bin/bash
#SBATCH --job-name=agent
#SBATCH --output=SLURM_Logs/agent%j.out
#SBATCH --error=SLURM_Logs/agent%j.err
#SBATCH --nodes=1
#SBATCH --cpus-per-task=2
#SBATCH --ntasks-per-node=1
#SBATCH --partition=cpu_p1
#SBATCH --account=tdm@cpu
#SBATCH --qos=qos_cpu-t3
#SBATCH --hint=nomultithread
#SBATCH --time=04:00:00

module purge
conda deactivate
source /lustre/fswork/projects/rech/tdm/commun/venv/crrrocq/bin/activate
cd $SCRATCH/crrrocq

python -m script.inference