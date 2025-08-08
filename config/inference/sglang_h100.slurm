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

ID=$RANDOM_$(date '+%Y_%m_%d_%H_%M_%S')

export RETRIEVAL_IP_PATH=/lustre/fsn1/projects/rech/tdm/commun/tmp/retrieval_ip_$ID.txt
export PET_IP_PATH=/lustre/fsn1/projects/rech/tdm/commun/tmp/pet_ip_$ID.txt
export MODEL_IP_PATH=/lustre/fsn1/projects/rech/tdm/commun/tmp/model_ip_$ID.txt
export EMBED_IP_PATH=/lustre/fsn1/projects/rech/tdm/commun/tmp/embed_ip_$ID.txt
export PET_RESTART_PATH=/lustre/fsn1/projects/rech/tdm/commun/tmp/pet_restart_$ID.txt
export PET_PORTS_PATH=/lustre/fsn1/projects/rech/tdm/commun/tmp/pet_ports_$ID.txt


module purge
module load arch/h100 cuda/12.8.0 nccl/2.25.1-1-cuda

source /lustre/fswork/projects/rech/tdm/commun/.opam/opam-init/init.sh
source /lustre/fswork/projects/rech/tdm/commun/venv/crrrocq/bin/activate

cd $SCRATCH/crrrocq

TP_SIZE=4
MODEL_PATH="/lustre/fsn1/projects/rech/tdm/commun/models/crrrocq_compress/"
MODEL_PORT=30000
EMBED_PATH="/lustre/fsn1/projects/rech/tdm/commun/hf_home/hub/models--Qwen--Qwen3-Embedding-4B/snapshots/5cf2132abc99cad020ac570b19d031efec650f2b"
EMBED_PORT=30001

FLASK_PET_PORT=5000
FLASK_RETRIEVAL_PORT=5001


HEAD_NODE=$(scontrol show hostname "$SLURM_NODELIST" | head -n 1)
NCCL_INIT_ADDR="${HEAD_NODE}:8000"
export SGLANG_HOST_IP="${HEAD_NODE}"

unset http_proxy
unset HTTP_PROXY
unset https_proxy
unset HTTPS_PROXY

python -m sglang.launch_server --tp-size $TP_SIZE --mem-fraction-static 0.7 --model-path $MODEL_PATH --host 0.0.0.0 --port $MODEL_PORT &
python -m sglang.launch_server --tp-size $TP_SIZE --mem-fraction-static 0.29 --model-path $EMBED_PATH --host 0.0.0.0 --port $EMBED_PORT  --is-embedding &

gunicorn -w 4 -b 0.0.0.0:$FLASK_PET_PORT src.servers.script.app:app -t 90 -c src/servers/script/gunicorn.config.py &
until curl -s -o /dev/null -w "%{http_code}" http://localhost:$FLASK_PET_PORT/health | grep -q "200"; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Waiting for pet server to respond..."
    sleep 20
done

echo $HEAD_NODE:$FLASK_PET_PORT > $PET_IP_PATH

until curl -s -o /dev/null -w "%{http_code}" http://localhost:$EMBED_PORT/v1/models | grep -q "200"; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Waiting for server to respond..."
    sleep 20
done
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Embedding ready."
echo $HEAD_NODE:$EMBED_PORT > $EMBED_IP_PATH

gunicorn -w 4 -b 0.0.0.0:$FLASK_RETRIEVAL_PORT src.servers.retrieval.app:app &
until curl -s -o /dev/null -w "%{http_code}" http://localhost:$FLASK_RETRIEVAL_PORT/health | grep -q "200"; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Waiting for retrieval server to respond..."
    sleep 20
done
echo $HEAD_NODE:$FLASK_RETRIEVAL_PORT > $RETRIEVAL_IP_PATH


until curl -s -o /dev/null -w "%{http_code}" http://localhost:$MODEL_PORT/v1/models | grep -q "200"; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Waiting for server to respond..."
    sleep 20
done

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Model ready."
echo "[$(date '+%Y-%m-%d %H:%M:%S')] SGLang ready."
echo $HEAD_NODE:$MODEL_PORT > $MODEL_IP_PATH

python -m script.inference