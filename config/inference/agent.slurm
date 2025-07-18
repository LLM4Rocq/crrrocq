#!/bin/bash
#SBATCH --job-name=agent
#SBATCH --output=SLURM_Logs/agent%j.out
#SBATCH --error=SLURM_Logs/agent%j.err
#SBATCH --nodes=1
#SBATCH --cpus-per-task=4
#SBATCH --ntasks-per-node=1
#SBATCH --partition=cpu_p1
#SBATCH --account=tdm@cpu
#SBATCH --qos=qos_cpu-dev
#SBATCH --hint=nomultithread
#SBATCH --time=01:00:00

module purge
conda deactivate
source /lustre/fswork/projects/rech/tdm/commun/venv/crrrocq/bin/activate
cd $SCRATCH/crrrocq

python -m inference.script