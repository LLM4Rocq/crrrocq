#!/bin/bash -l

#SBATCH --job-name=unified-inference
#SBATCH --output=SLURM_Logs/%x_%j_crrrocq.out
#SBATCH --error=SLURM_Logs/%x_%j_crrrocq.err
#SBATCH -D ./

#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=64
#SBATCH --gres=gpu:4
#SBATCH --time=02:00:00
#SBATCH --hint=nomultithread
#SBATCH --constraint=h100
#SBATCH --account=tdm@h100
#SBATCH --qos=qos_gpu_h100-dev

# Generate unique ID for this run
ID=$RANDOM_$(date '+%Y_%m_%d_%H_%M_%S')

export RETRIEVAL_IP_PATH=/lustre/fsn1/projects/rech/tdm/commun/tmp/retrieval_ip_$ID.txt
export PET_IP_PATH=/lustre/fsn1/projects/rech/tdm/commun/tmp/pet_ip_$ID.txt
export MODEL_IP_PATH=/lustre/fsn1/projects/rech/tdm/commun/tmp/model_ip_$ID.txt
export EMBED_IP_PATH=/lustre/fsn1/projects/rech/tdm/commun/tmp/embed_ip_$ID.txt
export PET_RESTART_PATH=/lustre/fsn1/projects/rech/tdm/commun/tmp/pet_restart_$ID.txt
export PET_PORTS_PATH=/lustre/fsn1/projects/rech/tdm/commun/tmp/pet_ports_$ID.txt

# Clean up any existing files
rm -f $RETRIEVAL_IP_PATH
rm -f $PET_IP_PATH
rm -f $MODEL_IP_PATH
rm -f $EMBED_IP_PATH
rm -f $PET_RESTART_PATH
rm -f $PET_PORTS_PATH

# Load modules and activate environment
module purge
module load arch/h100 cuda/12.8.0 nccl/2.25.1-1-cuda
source /lustre/fsn1/projects/rech/tdm/commun/venv/crrrocq/bin/activate

# SGLang configuration
TP_SIZE=4  # Use all 4 H100 GPUs
MODEL_PATH="/lustre/fsn1/projects/rech/tdm/commun/models/crrrocq_compress/"
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

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting all servers..."

# Start SGLang model server (using 3 GPUs with higher memory fraction)
CUDA_VISIBLE_DEVICES=0,1,2 python -m sglang.launch_server --tp-size $TP_SIZE --mem-fraction-static 0.7 --model-path $MODEL_PATH --host 0.0.0.0 --port $MODEL_PORT &
MODEL_PID=$!

# Start SGLang embedding server (using 1 GPU)
CUDA_VISIBLE_DEVICES=3 python -m sglang.launch_server --tp-size $TP_SIZE --mem-fraction-static 0.29 --model-path $EMBED_PATH --host 0.0.0.0 --port $EMBED_PORT --is-embedding &
EMBED_PID=$!


cd $SCRATCH/crrrocq

# Start PET server on CPU
source /lustre/fswork/projects/rech/tdm/commun/.opam/opam-init/init.sh
FLASK_PORT=5000
gunicorn -w 4 -b 0.0.0.0:$FLASK_PORT src.servers.script.app:app -t 90 -c src/servers/script/gunicorn.config.py &
PET_PID=$!

# Start Retrieval server on CPU
RETRIEVAL_PORT=5001
gunicorn -w 8 -b 0.0.0.0:$RETRIEVAL_PORT src.servers.retrieval.app:app &
RETRIEVAL_PID=$!

# Wait loop for all services
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Waiting for all services to be ready..."

while true; do
    model_ready=false
    embed_ready=false
    pet_ready=false
    retrieval_ready=false
    
    # Check model server
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:$MODEL_PORT/v1/models | grep -q "200"; then
        model_ready=true
        if [ ! -f "$MODEL_IP_PATH" ]; then
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] Model server ready."
            echo $HEAD_NODE:$MODEL_PORT > $MODEL_IP_PATH
        fi
    fi
    
    # Check embedding server
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:$EMBED_PORT/v1/models | grep -q "200"; then
        embed_ready=true
        if [ ! -f "$EMBED_IP_PATH" ]; then
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] Embedding server ready."
            echo $HEAD_NODE:$EMBED_PORT > $EMBED_IP_PATH
        fi
    fi
    
    # Check PET server
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:$FLASK_PORT/health | grep -q "200"; then
        pet_ready=true
        if [ ! -f "$PET_IP_PATH" ]; then
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] PET server ready."
            echo $HEAD_NODE:$FLASK_PORT > $PET_IP_PATH
        fi
    fi
    
    # Check retrieval server
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:$RETRIEVAL_PORT/health | grep -q "200"; then
        retrieval_ready=true
        if [ ! -f "$RETRIEVAL_IP_PATH" ]; then
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] Retrieval server ready."
            echo $HEAD_NODE:$RETRIEVAL_PORT > $RETRIEVAL_IP_PATH
        fi
    fi
    
    # Break if all services are ready
    if [ "$model_ready" = true ] && [ "$embed_ready" = true ] && [ "$pet_ready" = true ] && [ "$retrieval_ready" = true ]; then
        break
    fi
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Waiting for services... (Model: $model_ready, Embed: $embed_ready, PET: $pet_ready, Retrieval: $retrieval_ready)"
    sleep 20
done

echo "[$(date '+%Y-%m-%d %H:%M:%S')] All services ready. Starting agent..."

# Start Agent on CPU
python -m script.inference &
AGENT_PID=$!

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Agent started."

# Function to cleanup background processes on exit
cleanup() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Cleaning up processes..."
    kill $MODEL_PID $EMBED_PID $PET_PID $RETRIEVAL_PID $AGENT_PID 2>/dev/null
    wait
}

trap cleanup EXIT

# Wait for the end of the job
wait