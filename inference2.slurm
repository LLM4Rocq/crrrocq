#!/bin/bash

#SBATCH --job-name=infer-test         # name of the job
#SBATCH --nodes=1                     # number of nodes
#SBATCH --ntasks-per-node=1           # number of MPI tasks per node
#SBATCH --hint=nomultithread          # reservation of physical cores (no hyperthreading)
#SBATCH --output=infer-test%j.out     # name of output file
#SBATCH --error=infer-test%j.err      # name of error file
#SBATCH --constraint=h100             # h100 gpus
#SBATCH --nodes=1                     # number of nodes
#SBATCH --gres=gpu:2                  # number of gpus/node
#SBATCH --time=01:00:00               # maximum execution time requested (HH:MM:SS)
#SBATCH --account=tdm@h100            # account
#SBATCH --qos=qos_gpu_h100-dev

# clean out the modules loaded in interactive and inherited by default
module purge
module load arch/h100 cuda/12.8.0 nccl/2.25.1-1-cuda
pkill pet-server

# Detect available NUMA nodes and system topology
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Detecting system topology..."

# Detect GPU to NUMA mapping
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Detecting GPU to NUMA mapping..."

# Get NUMA affinity for each GPU
GPU0_NUMA=$(nvidia-smi topo -m | grep "^GPU0" | awk '{print $8}')
GPU1_NUMA=$(nvidia-smi topo -m | grep "^GPU1" | awk '{print $8}')

echo "GPU 0 (embedding server) -> NUMA node $GPU0_NUMA"
echo "GPU 1 (main server) -> NUMA node $GPU1_NUMA"

# Validate that we got valid NUMA nodes
if [[ ! "$GPU0_NUMA" =~ ^[0-9]+$ ]] || [[ ! "$GPU1_NUMA" =~ ^[0-9]+$ ]]; then
    echo "Warning: Could not detect GPU NUMA mapping, using fallback detection"
    # Fallback: check sysfs for GPU NUMA nodes
    GPU0_NUMA=$(cat /sys/class/drm/card0/device/numa_node 2>/dev/null || echo "0")
    GPU1_NUMA=$(cat /sys/class/drm/card1/device/numa_node 2>/dev/null || echo "1")
    echo "Fallback: GPU 0 -> NUMA node $GPU0_NUMA, GPU 1 -> NUMA node $GPU1_NUMA"
fi

# Set NUMA commands for optimal placement (use flexible binding to avoid affinity errors)
EMBEDDING_NUMA_CMD="numactl --preferred=$GPU0_NUMA"
MAIN_NUMA_CMD="numactl --preferred=$GPU1_NUMA"
PET_NUMA_CMD="numactl --preferred=$GPU0_NUMA"  # Same as embedding server
INFERENCE_NUMA_CMD="numactl --preferred=$GPU0_NUMA"  # Same as embedding server

echo "NUMA commands configured (using --preferred for flexibility):"
echo "  Embedding server: $EMBEDDING_NUMA_CMD"
echo "  Main server: $MAIN_NUMA_CMD" 
echo "  pet-server: $PET_NUMA_CMD"
echo "  Inference: $INFERENCE_NUMA_CMD"

# Test NUMA commands before using them
echo "Testing NUMA commands..."
if ! $EMBEDDING_NUMA_CMD echo "test" >/dev/null 2>&1; then
    echo "Warning: NUMA binding for GPU0 node $GPU0_NUMA failed, disabling"
    EMBEDDING_NUMA_CMD=""
    PET_NUMA_CMD=""
    INFERENCE_NUMA_CMD=""
fi

if ! $MAIN_NUMA_CMD echo "test" >/dev/null 2>&1; then
    echo "Warning: NUMA binding for GPU1 node $GPU1_NUMA failed, disabling"
    MAIN_NUMA_CMD=""
fi

# Activate virtual env
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Activating environment"
source /lustre/fswork/projects/rech/tdm/commun/venv/crrrocq/bin/activate

# echo commands
set -x

# do not store tmp files in /tmp!
export TMPDIR=$JOBSCRATCH

MODEL=/lustre/fsn1/projects/rech/tdm/commun/models/crrrocq_base/
MODEL_EMB=/lustre/fsn1/projects/rech/tdm/commun/hf_home/hub/models--Qwen--Qwen3-Embedding-4B/snapshots/5cf2132abc99cad020ac570b19d031efec650f2b
WORKSPACE=examples
THM=foo
FILE=foo.v
PORT_EMB=31000

# Clean up any existing servers
pkill -f sglang.launch_server
sleep 5

# Check available GPUs
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Checking available GPUs..."
nvidia-smi --list-gpus
GPU_COUNT=$(nvidia-smi --list-gpus | wc -l)
echo "Found $GPU_COUNT GPUs"

if [[ $GPU_COUNT -lt 2 ]]; then
    echo "ERROR: Need at least 2 GPUs, only found $GPU_COUNT"
    exit 1
fi

# Launch embedding server on GPU 0 with NUMA binding
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Launching embedding server on GPU 0 (NUMA node $GPU0_NUMA)..."
if [[ -n "$EMBEDDING_NUMA_CMD" ]]; then
    CUDA_VISIBLE_DEVICES=0 $EMBEDDING_NUMA_CMD python -m sglang.launch_server --model-path $MODEL_EMB --host 0.0.0.0 --port $PORT_EMB --is-embedding > embedding_server.log 2>&1 &
else
    echo "Using no NUMA binding for embedding server"
    CUDA_VISIBLE_DEVICES=0 python -m sglang.launch_server --model-path $MODEL_EMB --host 0.0.0.0 --port $PORT_EMB --is-embedding > embedding_server.log 2>&1 &
fi
EMB_PID=$!

# Wait for embedding server to initialize
sleep 30

# Check if embedding server is still running
if ! kill -0 $EMB_PID 2>/dev/null; then
    echo "ERROR: Embedding server died, check embedding_server.log"
    cat embedding_server.log
    exit 1
fi

# Launch main server on GPU 1 with NUMA binding
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Launching main server on GPU 1 (NUMA node $GPU1_NUMA)..."
if [[ -n "$MAIN_NUMA_CMD" ]]; then
    CUDA_VISIBLE_DEVICES=1 $MAIN_NUMA_CMD python -m sglang.launch_server \
        --model-path $MODEL \
        --host 0.0.0.0 \
        --port 30000 \
        --mem-fraction-static 0.8 \
        --disable-radix-cache \
        --max-running-requests 1 > main_server.log 2>&1 &
else
    echo "Using no NUMA binding for main server"
    CUDA_VISIBLE_DEVICES=1 python -m sglang.launch_server \
        --model-path $MODEL \
        --host 0.0.0.0 \
        --port 30000 \
        --mem-fraction-static 0.8 \
        --disable-radix-cache \
        --max-running-requests 1 > main_server.log 2>&1 &
fi
MAIN_PID=$!

# Wait longer for main server to initialize
echo "Waiting 60 seconds for main server to fully initialize..."
sleep 60

# Check if main server is still running
if ! kill -0 $MAIN_PID 2>/dev/null; then
    echo "ERROR: Main server died during startup, check main_server.log"
    echo "=== Main Server Log ==="
    cat main_server.log
    echo "=== GPU Status ==="
    nvidia-smi
    exit 1
fi

echo "Main server still running, checking GPU memory usage..."
nvidia-smi --query-gpu=index,memory.used,memory.total --format=csv

# Wait for server to respond with more robust checking
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Waiting for servers to respond..."

# Check embedding server
echo "Checking embedding server on port $PORT_EMB..."
for i in {1..10}; do
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:$PORT_EMB/v1/models | grep -q "200"; then
        echo "✓ Embedding server responding on port $PORT_EMB"
        break
    elif [[ $i -eq 10 ]]; then
        echo "✗ Embedding server not responding after 10 attempts"
        echo "Server logs:"
        tail -20 embedding_server.log
        exit 1
    else
        echo "Attempt $i/10: Embedding server not ready, waiting..."
        sleep 30
    fi
done

# Check main server with timeout
echo "Checking main server on port 30000..."
for i in {1..15}; do
    # Use timeout to prevent hanging
    if timeout 10 curl -s -f http://localhost:30000/v1/models >/dev/null 2>&1; then
        echo "✓ Main server responding on port 30000"
        # Test actual inference endpoint
        if timeout 10 curl -s -f http://localhost:30000/health >/dev/null 2>&1; then
            echo "✓ Main server health check passed"
        else
            echo "⚠ Main server responds to /v1/models but not /health"
        fi
        break
    elif [[ $i -eq 15 ]]; then
        echo "✗ Main server not responding after 15 attempts"
        echo "=== Main Server Log (last 50 lines) ==="
        tail -50 main_server.log
        echo "=== Process Status ==="
        ps aux | grep -E "sglang.*30000" | grep -v grep
        echo "=== Port Status ==="
        ss -tlnp | grep :30000
        echo "=== GPU Memory ==="
        nvidia-smi --query-gpu=memory.used,memory.total --format=csv
        
        # Try to get more detailed connection info
        echo "=== Testing connection manually ==="
        timeout 5 telnet localhost 30000 < /dev/null
        exit 1
    else
        echo "Attempt $i/15: Main server not ready, waiting..."
        # Check if process died
        if ! kill -0 $MAIN_PID 2>/dev/null; then
            echo "ERROR: Main server process died!"
            echo "=== Main Server Log ==="
            cat main_server.log
            exit 1
        fi
        sleep 20
    fi
done

# Additional connectivity tests
echo "Testing server connectivity..."
curl -v http://localhost:30000/v1/models 2>&1 | head -10
echo "Server process status:"
ps aux | grep -E "(sglang|python.*sglang)" | grep -v grep

# go into the submission directory 
cd $WORK/GitHub/crrrocq 

# launch pet-server on same NUMA node as embedding server
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Launching pet-server on NUMA node $GPU0_NUMA (same as embedding server)..."
if [[ -n "$PET_NUMA_CMD" ]]; then
    $PET_NUMA_CMD pet-server > pet_server.log 2>&1 &
else
    echo "Using no NUMA binding for pet-server"
    pet-server > pet_server.log 2>&1 &
fi
PET_PID=$!

# Verify pet-server is running and check its location
sleep 5
if ps -p $PET_PID > /dev/null; then
    echo "✓ pet-server running on PID: $PET_PID"
    echo "  Running on CPU: $(ps -o psr= -p $PET_PID)"
    echo "  NUMA binding: $(numactl --show $PET_PID 2>/dev/null | grep -E 'nodebind|cpubind' || echo 'No explicit binding')"
    
    # Verify it's on the correct NUMA node
    actual_node=$(numactl --show $PET_PID 2>/dev/null | grep "nodebind:" | awk '{print $2}')
    if [[ "$actual_node" == "$GPU0_NUMA" ]]; then
        echo "  ✓ Correctly placed on NUMA node $GPU0_NUMA"
    else
        echo "  ⚠ Expected NUMA node $GPU0_NUMA but got $actual_node"
    fi
else
    echo "✗ pet-server failed to start, check pet_server.log"
    cat pet_server.log
    exit 1
fi

# launch inference on same NUMA node as embedding server
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Launching inference on NUMA node $GPU0_NUMA (same as embedding server)..."
if [[ -n "$INFERENCE_NUMA_CMD" ]]; then
    $INFERENCE_NUMA_CMD python -m src.inference.inference-cli --theorem $THM --file $FILE --workspace $WORKSPACE --model $MODEL
else
    echo "Using no NUMA binding for inference"
    python -m src.inference.inference-cli --theorem $THM --file $FILE --workspace $WORKSPACE --model $MODEL
fi

# Keep the script running until the SLURM job times out
wait