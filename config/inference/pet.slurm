#!/bin/bash
#SBATCH --job-name=pet
#SBATCH --output=SLURM_Logs/pet%j.out
#SBATCH --error=SLURM_Logs/pet%j.err
#SBATCH --nodes=1
#SBATCH --cpus-per-task=2
#SBATCH --ntasks-per-node=4
#SBATCH --partition=cpu_p1
#SBATCH --account=tdm@cpu
#SBATCH --qos=qos_cpu-dev
#SBATCH --hint=nomultithread
#SBATCH --time=02:00:00

module purge
conda deactivate

source /lustre/fswork/projects/rech/tdm/commun/.opam/opam-init/init.sh
source /lustre/fswork/projects/rech/tdm/commun/venv/crrrocq/bin/activate

HEAD_NODE=$(scontrol show hostname "$SLURM_NODELIST" | head -n 1)
export BASE_PORT=8765

srun --export=ALL bash -lc '
  source /lustre/fswork/projects/rech/tdm/commun/.opam/opam-init/init.sh
  source /lustre/fswork/projects/rech/tdm/commun/venv/crrrocq/bin/activate
  PORT=$(( BASE_PORT + SLURM_PROCID ))      # unique port per task
  echo "Task $SLURM_PROCID listening on $PORT"
  pet-server -p "$PORT"
' &

sleep 10
echo $HEAD_NODE > /lustre/fsn1/projects/rech/tdm/commun/pet_ip.txt
cd src/servers/script

gunicorn -w 9 -b 0.0.0.0:5000 app:app

wait