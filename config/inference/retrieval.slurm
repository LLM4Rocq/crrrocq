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
FLASK_PORT=5001
HEAD_NODE=$(scontrol show hostname "$SLURM_NODELIST" | head -n 1)

# srun --export=ALL bash -lc '
#   source /lustre/fswork/projects/rech/tdm/commun/venv/crrrocq/bin/activate
# ' &
# 
# sleep 60

gunicorn -w 8 -b 0.0.0.0:$FLASK_PORT src.servers.retrieval.app:app &
until curl -s -o /dev/null -w "%{http_code}" http://localhost:$FLASK_PORT/health | grep -q "200"; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Waiting for retrieval server to respond..."
    sleep 20
done

echo $HEAD_NODE:$FLASK_PORT > $RETRIEVAL_IP_PATH

wait