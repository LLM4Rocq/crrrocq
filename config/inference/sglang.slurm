#!/bin/bash -l

#SBATCH --job-name=sglang
#SBATCH --output SLURM_Logs/%x_%j_sglang.out
#SBATCH --error SLURM_Logs/%x_%j_sglang.err
#SBATCH -D ./

#SBATCH --nodes=1
#SBATCH --ntasks=1                   # 1 task par nodes
#SBATCH --ntasks-per-node=1           # Each task will see all GPUs of the node
#SBATCH --cpus-per-task=64
#SBATCH --gres=gpu:8
#SBATCH --time=04:00:00
#SBATCH --hint=nomultithread          # no hyperthreading
#SBATCH --constraint=a100             # h100 gpus
#SBATCH --account=tdm@a100            # account
#SBATCH --qos=qos_gpu_a100-t3

module purge
module load arch/h100 cuda/12.8.0 nccl/2.25.1-1-cuda
source /lustre/fswork/projects/rech/tdm/commun/venv/crrrocq/bin/activate

TP_SIZE=8
MODEL_PATH="/lustre/fsn1/projects/rech/tdm/commun/models/crrrocq_base/"
MODEL_PORT=30000
EMBED_PATH="/lustre/fsn1/projects/rech/tdm/commun/hf_home/hub/models--Qwen--Qwen3-Embedding-4B/snapshots/5cf2132abc99cad020ac570b19d031efec650f2b"
EMBED_PORT=30001

HEAD_NODE=$(scontrol show hostname "$SLURM_NODELIST" | head -n 1)
NCCL_INIT_ADDR="${HEAD_NODE}:8000"
export SGLANG_HOST_IP="${HEAD_NODE}"

unset http_proxy
unset HTTP_PROXY
unset https_proxy
unset HTTPS_PROXY

python -m sglang.launch_server --tp-size $TP_SIZE --mem-fraction-static 0.7 --model-path $MODEL_PATH --host 0.0.0.0 --port $MODEL_PORT &
python -m sglang.launch_server --tp-size $TP_SIZE --mem-fraction-static 0.29 --model-path $EMBED_PATH --host 0.0.0.0 --port $EMBED_PORT  --is-embedding &

sleep 60

# This logic (wait/run) should probably be implemented in the python script for inference...

# srun --overlap --nodes=1 --nodelist=$HEAD_NODE\
#      sh <<'EOF'

until curl -s -o /dev/null -w "%{http_code}" http://localhost:$EMBED_PORT/v1/models | grep -q "200"; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Waiting for server to respond..."
    sleep 20
done
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Embedding ready."
echo $HEAD_NODE:$EMBED_PORT > $EMBED_IP_PATH

until curl -s -o /dev/null -w "%{http_code}" http://localhost:$MODEL_PORT/v1/models | grep -q "200"; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Waiting for server to respond..."
    sleep 20
done

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Model ready."
echo "[$(date '+%Y-%m-%d %H:%M:%S')] SGLang ready."
echo $HEAD_NODE:$MODEL_PORT > $MODEL_IP_PATH

# Keep the script running until the SLURM job times out

wait