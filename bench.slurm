#!/bin/bash

#SBATCH --job-name=bench-test         # name of the job
#SBATCH --nodes=1                     # number of nodes
#SBATCH --ntasks-per-node=1           # number of MPI tasks per node
#SBATCH --hint=nomultithread          # reservation of physical cores (no hyperthreading)
#SBATCH --output=bench-test%j.out  # name of output file
#SBATCH --error=bench-test%j.err   # name of error file
#SBATCH --constraint=h100             # h100 gpus
#SBATCH --nodes=1                     # number of nodes
#SBATCH --gres=gpu:2                  # number of gpus/node
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
LOG_DIR=bench_$(date +%Y%m%d_%H%M%S)
PORT_EMB=31000
MAX_WORKERS=8
MAX_THEOREMS=16  # Adjust based on your needs
NUM_ATTEMPT=8
MAX_ITERATIONS=100

# Function to detect GPU-CPU topology automatically
detect_gpu_topology() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Detecting GPU-CPU topology..."
    
    # Check if nvidia-smi is available and get topology
    if command -v nvidia-smi &> /dev/null; then
        # Get GPU count
        GPU_COUNT=$(nvidia-smi --query-gpu=index --format=csv,noheader,nounits | wc -l)
        echo "Found $GPU_COUNT GPUs"
        
        # Get CPU affinity for each GPU
        nvidia-smi topo -m > /tmp/gpu_topology.txt
        
        # Parse CPU affinity for GPU0 and GPU1 - skip header row
        GPU0_CPUS=$(nvidia-smi topo -m | grep "^GPU0" | awk '{print $8}')
        GPU1_CPUS=$(nvidia-smi topo -m | grep "^GPU1" | awk '{print $8}')
        
        # Get NUMA affinity - extract field 9 for both GPUs, skip header row
        GPU0_NUMA=$(nvidia-smi topo -m | grep "^GPU0" | awk '{print $9}')
        GPU1_NUMA=$(nvidia-smi topo -m | grep "^GPU1" | awk '{print $9}')
        
        echo "GPU0 CPU affinity: $GPU0_CPUS, NUMA: $GPU0_NUMA"
        echo "GPU1 CPU affinity: $GPU1_CPUS, NUMA: $GPU1_NUMA"
        
        # If NUMA info is available and valid (numeric), use it
        if [[ "$GPU0_NUMA" =~ ^[0-9]+$ ]] && [[ "$GPU1_NUMA" =~ ^[0-9]+$ ]] && [[ "$GPU0_NUMA" != "N/A" ]] && [[ "$GPU1_NUMA" != "N/A" ]]; then
            EMB_NUMA_NODE=$GPU0_NUMA  # Embedding server uses GPU0
            MAIN_NUMA_NODE=$GPU1_NUMA # Main server uses GPU1
            USE_NUMA=true
            echo "Using NUMA nodes: Main=$MAIN_NUMA_NODE, Embedding=$EMB_NUMA_NODE"
        else
            echo "NUMA info not available or invalid, using CPU ranges"
            USE_NUMA=false
            # Clean up CPU ranges - remove any non-numeric characters except digits, commas, and hyphens
            EMB_CPUS=$(echo "$GPU0_CPUS" | grep -o '[0-9,-]*')
            MAIN_CPUS=$(echo "$GPU1_CPUS" | grep -o '[0-9,-]*')
            echo "Using CPU ranges: Main=$MAIN_CPUS, Embedding=$EMB_CPUS"
        fi
    else
        echo "nvidia-smi not available, using fallback CPU allocation"
        USE_NUMA=false
        # Fallback: split available CPUs evenly
        TOTAL_CPUS=$(nproc)
        HALF_CPUS=$((TOTAL_CPUS / 2))
        MAIN_CPUS="0-$((HALF_CPUS - 1))"
        EMB_CPUS="$HALF_CPUS-$((TOTAL_CPUS - 1))"
    fi
}

# Function to start server with optimal CPU binding
start_server_with_binding() {
    local server_type=$1
    local gpu_id=$2
    local command=$3
    local cpu_binding=$4
    local numa_node=$5
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting $server_type server with GPU $gpu_id"
    
    if [[ "$USE_NUMA" == "true" ]] && [[ "$numa_node" =~ ^[0-9]+$ ]]; then
        # Use NUMA binding
        echo "Using NUMA node $numa_node"
        numactl --cpunodebind=$numa_node --membind=$numa_node $command &
    elif [[ -n "$cpu_binding" ]]; then
        # Use CPU range binding
        echo "Using CPU range $cpu_binding"
        taskset -c $cpu_binding $command &
    else
        # No binding - let system decide
        echo "No CPU binding, using system default"
        $command &
    fi
}

# Detect topology
detect_gpu_topology

# Start main server (GPU1)
start_server_with_binding "main" 1 \
    "python -m sglang.launch_server --model-path $MODEL --base-gpu-id 1 --host 0.0.0.0" \
    "$MAIN_CPUS" "$MAIN_NUMA_NODE"
MAIN_PID=$!

# Start embedding server (GPU0)  
start_server_with_binding "embedding" 0 \
    "python -m sglang.launch_server --model-path $MODEL_EMB --base-gpu-id 0 --host 0.0.0.0 --port $PORT_EMB --is-embedding" \
    "$EMB_CPUS" "$EMB_NUMA_NODE"
EMB_PID=$!

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
if [[ "$USE_NUMA" == "true" ]] && [[ "$EMB_NUMA_NODE" =~ ^[0-9]+$ ]]; then
    numactl --cpunodebind=$EMB_NUMA_NODE --membind=$EMB_NUMA_NODE pet-server &
elif [[ -n "$EMB_CPUS" ]]; then
    taskset -c $EMB_CPUS pet-server &
else
    pet-server &
fi
PET_PID=$!

# Give pet-server time to start
sleep 5

# Run benchmark
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting benchmark with $MAX_WORKERS workers on $MAX_THEOREMS theorems"
if [[ "$USE_NUMA" == "true" ]] && [[ "$EMB_NUMA_NODE" =~ ^[0-9]+$ ]]; then
    numactl --cpunodebind=$EMB_NUMA_NODE --membind=$EMB_NUMA_NODE python -m src.inference.benchmark \
        --evaluation-json $EVALUATION_JSON \
        --max-workers $MAX_WORKERS \
        --max-theorems $MAX_THEOREMS \
        --num-attempt $NUM_ATTEMPT \
        --max-iterations $MAX_ITERATIONS \
        --log-dir $LOG_DIR \
        --verbose
elif [[ -n "$EMB_CPUS" ]]; then
    taskset -c $EMB_CPUS python -m src.inference.benchmark \
        --evaluation-json $EVALUATION_JSON \
        --max-workers $MAX_WORKERS \
        --max-theorems $MAX_THEOREMS \
        --num-attempt $NUM_ATTEMPT \
        --max-iterations $MAX_ITERATIONS \
        --log-dir $LOG_DIR \
        --verbose
else
    python -m src.inference.benchmark \
        --evaluation-json $EVALUATION_JSON \
        --max-workers $MAX_WORKERS \
        --max-theorems $MAX_THEOREMS \
        --num-attempt $NUM_ATTEMPT \
        --max-iterations $MAX_ITERATIONS \
        --log-dir $LOG_DIR \
        --verbose
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Benchmark completed"

# Log final resource usage
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Resource usage summary:"
echo "Main server PID: $MAIN_PID"
echo "Embedding server PID: $EMB_PID"
echo "Pet server PID: $PET_PID"

# Optional: Clean shutdown
kill $PET_PID 2>/dev/null
kill $EMB_PID 2>/dev/null  
kill $MAIN_PID 2>/dev/null

wait