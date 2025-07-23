#!/bin/bash

#SBATCH --job-name=bench-fn         # name of the job
#SBATCH --nodes=1                     # number of nodes
#SBATCH --ntasks-per-node=1           # number of MPI tasks per node
#SBATCH --hint=nomultithread          # reservation of physical cores (no hyperthreading)
#SBATCH --output=bench_logs/bench-fn%j.out     # name of output file
#SBATCH --error=bench_logs/bench-fn%j.err      # name of error file
#SBATCH --constraint=h100             # h100 gpus
#SBATCH --nodes=1                     # number of nodes
#SBATCH --gres=gpu:4                  # number of gpus/node 
#SBATCH --cpus-per-task=48            # total CPUs available
#SBATCH --time=02:00:00               # maximum execution time requested (HH:MM:SS)
#SBATCH --account=tdm@h100            # account
#SBATCH --qos=qos_gpu_h100-dev

# clean out the modules loaded in interactive and inherited by default
module purge
module load arch/h100 cuda/12.8.0 nccl/2.25.1-1-cuda
pkill pet-server

# Activate virtual env
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Activating environment" 
source /lustre/fswork/projects/rech/tdm/commun/venv/crrrocq/bin/activate

# echo commands
set -x

# do not store tmp files in /tmp!
export TMPDIR=$JOBSCRATCH

MODEL=/lustre/fsn1/projects/rech/tdm/commun/models/crrrocq_base/
MODEL_EMB=/lustre/fsn1/projects/rech/tdm/commun/hf_home/hub/models--Qwen--Qwen3-Embedding-4B/snapshots/5cf2132abc99cad020ac570b19d031efec650f2b
EVALUATION_JSON=/lustre/fsn1/projects/rech/tdm/commun/dataset/evaluation.json
LOG_DIR=/lustre/fsn1/projects/rech/tdm/uuz44ie/experiments-crrrocq/bench_$(date +%Y%m%d_%H%M%S)
PORT_EMB=31000
MAX_WORKERS=${MAX_WORKERS:-32}
MAX_THEOREMS=${MAX_THEOREMS:-150}
NUM_ATTEMPT=${NUM_ATTEMPT:-32}
NUM_FULL_ATTEMPT=${NUM_FULL_ATTEMPT:-32}
MAX_ITERATIONS=100

python -m sglang.launch_server --model-path $MODEL --tp-size 4 --mem-fraction-static 0.7 --host 0.0.0.0 &
python -m sglang.launch_server --model-path $MODEL_EMB --base-gpu-id 2 --tp-size 2 --mem-fraction-static 0.29 --host 0.0.0.0 --port $PORT_EMB --is-embedding &


# Wait for main server to be ready
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Waiting for main server to be ready..."
MAX_RETRIES=60  # Increased from 30 to 60 (10 minutes total)
RETRY_COUNT=0
until curl -s -o /dev/null -w "%{http_code}" http://localhost:30000/v1/models | grep -q "200"; do
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "Main server failed to start within timeout"
        exit 1
    fi
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Waiting for main server to respond... (attempt $((RETRY_COUNT + 1))/$MAX_RETRIES)"
    sleep 10
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

# Wait for embedding server to be ready
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Waiting for embedding server to be ready..."
RETRY_COUNT=0
until curl -s -o /dev/null -w "%{http_code}" http://localhost:$PORT_EMB/v1/models | grep -q "200"; do
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "Embedding server failed to start within timeout"
        exit 1
    fi
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Waiting for embedding server to respond... (attempt $((RETRY_COUNT + 1))/$MAX_RETRIES)"
    sleep 10
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

# go into the submission directory 
cd $WORK/GitHub/crrrocq 

# Start pet-server and inference on same resources as embedding server
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting pet-server"
pet-server &

# Give pet-server time to start
sleep 5

# Run benchmark
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting benchmark with $MAX_WORKERS workers on $MAX_THEOREMS theorems"
python -m src.inference.benchmark \
        --evaluation-json $EVALUATION_JSON \
        --max-workers $MAX_WORKERS \
        --max-theorems $MAX_THEOREMS \
        --num-attempt $NUM_ATTEMPT \
        --max-iterations $MAX_ITERATIONS \
        --log-dir $LOG_DIR \
        --num-full-attempt $NUM_FULL_ATTEMPT \
        --verbose

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Benchmark completed"
