#!/bin/bash -l

#SBATCH --job-name=sglang
#SBATCH --output SLURM_Logs/%x_%j_sglang.out
#SBATCH --error SLURM_Logs/%x_%j_sglang.err
#SBATCH -D ./

#SBATCH --nodes=1
#SBATCH --ntasks=1                   # 1 task par nodes
#SBATCH --ntasks-per-node=1           # Each task will see all GPUs of the node
#SBATCH --cpus-per-task=96
#SBATCH --gres=gpu:4
#SBATCH --time=02:00:00
#SBATCH --hint=nomultithread          # no hyperthreading
#SBATCH --constraint=h100             # h100 gpus
#SBATCH --account=tdm@h100            # account
#SBATCH --qos=qos_gpu_h100-dev

module purge
module load arch/h100 cuda/12.8.0 nccl/2.25.1-1-cuda
source /lustre/fswork/projects/rech/tdm/commun/venv/crrrocq/bin/activate

TP_SIZE=4

HEAD_NODE=$(scontrol show hostname "$SLURM_NODELIST" | head -n 1)
NCCL_INIT_ADDR="${HEAD_NODE}:8000"
export SGLANG_HOST_IP="${HEAD_NODE}"

MODEL="/lustre/fsn1/projects/rech/tdm/commun/models/crrrocq_base/"
MODEL_PORT=30000
EMBED_MODEL="/lustre/fsn1/projects/rech/tdm/commun/hf_home/hub/models--Qwen--Qwen3-Embedding-4B/snapshots/5cf2132abc99cad020ac570b19d031efec650f2b"
EMBED_PORT=30001

unset http_proxy
unset HTTP_PROXY
unset https_proxy
unset HTTPS_PROXY

python -m sglang.launch_server --tp-size 4 --model-path $MODEL --host 0.0.0.0 --port $MODEL_PORT &
python -m sglang.launch_server --tp-size 4 --model-path $MODEL_EMB --host 0.0.0.0 --port $PORT_EMB --is-embedding &

sleep 60

# This logic (wait/run) should probably be implemented in the python script for inference...

srun --overlap --nodes=1 --nodelist=$HEAD_NODE\
     sh <<'EOF'

until curl -s -o /dev/null -w "%{http_code}" http://localhost:30000/v1/models | grep -q "200"; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Waiting for server to respond..."
    sleep 60
done

echo "[$(date '+%Y-%m-%d %H:%M:%S')] SGlang ready."
echo $HEAD_NODE > /lustre/fsn1/projects/rech/tdm/commun/retrieval_ip.txt

EOF

# Keep the script running until the SLURM job times out

wait