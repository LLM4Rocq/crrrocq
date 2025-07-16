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

# Check available NUMA nodes more carefully
echo "Full NUMA hardware info:"
numactl --hardware

# Get available nodes from /sys filesystem (more reliable)
if [[ -d /sys/devices/system/node ]]; then
    AVAILABLE_NODES=$(ls /sys/devices/system/node/ | grep "^node[0-9]" | sed 's/node//' | sort -n | tr '\n' ' ')
    echo "Available NUMA nodes from /sys: $AVAILABLE_NODES"
else
    # Fallback to numactl
    AVAILABLE_NODES=$(numactl --hardware | grep "available:" | cut -d' ' -f2)
    echo "Available NUMA nodes from numactl: $AVAILABLE_NODES"
fi

# Check total CPUs
TOTAL_CPUS=$(nproc)
echo "Total CPUs: $TOTAL_CPUS"

# Validate nodes exist
VALID_NODES=""
for node in $AVAILABLE_NODES; do
    if [[ -d "/sys/devices/system/node/node$node" ]]; then
        VALID_NODES="$VALID_NODES $node"
    fi
done
VALID_NODES=$(echo $VALID_NODES | xargs)  # trim whitespace
echo "Valid NUMA nodes: $VALID_NODES"

# Set preferred node (default to 0 if available, otherwise first valid)
if [[ "$VALID_NODES" == *"0"* ]]; then
    PREFERRED_NODE=0
    echo "Will use NUMA node 0"
elif [[ -n "$VALID_NODES" ]]; then
    PREFERRED_NODE=$(echo $VALID_NODES | cut -d' ' -f1)
    echo "Node 0 not available, using node $PREFERRED_NODE"
else
    PREFERRED_NODE=""
    echo "No valid NUMA nodes found"
fi

# Set NUMA command based on what's available
if command -v numactl &> /dev/null && [[ -n "$PREFERRED_NODE" ]] && [[ -d "/sys/devices/system/node/node$PREFERRED_NODE" ]]; then
    # Use only --preferred (allows flexible allocation) or --membind (strict binding)
    # Start with --preferred as it's less restrictive
    NUMA_CMD="numactl --preferred=$PREFERRED_NODE"
    echo "Using NUMA binding: $NUMA_CMD"
else
    NUMA_CMD=""
    echo "NUMA binding not available or invalid, running without binding"
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

# Launch embedding server on GPU 0
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Launching embedding server on GPU 0..."
CUDA_VISIBLE_DEVICES=0 python -m sglang.launch_server --model-path $MODEL_EMB --host 0.0.0.0 --port $PORT_EMB --is-embedding > embedding_server.log 2>&1 &
EMB_PID=$!

# Wait for embedding server to initialize
sleep 30

# Check if embedding server is still running
if ! kill -0 $EMB_PID 2>/dev/null; then
    echo "ERROR: Embedding server died, check embedding_server.log"
    cat embedding_server.log
    exit 1
fi

# Launch main server on GPU 1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Launching main server on GPU 1..."
CUDA_VISIBLE_DEVICES=1 python -m sglang.launch_server --model-path $MODEL --host 0.0.0.0 --port 30000 > main_server.log 2>&1 &
MAIN_PID=$!

# Wait for main server to initialize
sleep 30

# Check if main server is still running
if ! kill -0 $MAIN_PID 2>/dev/null; then
    echo "ERROR: Main server died, check main_server.log"
    cat main_server.log
    exit 1
fi

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
        sleep 60
    fi
done

# Check main server
echo "Checking main server on port 30000..."
for i in {1..10}; do
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:30000/v1/models | grep -q "200"; then
        echo "✓ Main server responding on port 30000"
        break
    elif [[ $i -eq 10 ]]; then
        echo "✗ Main server not responding after 10 attempts"
        echo "Server logs:"
        tail -20 main_server.log
        echo "Checking if process is still running:"
        ps aux | grep sglang
        echo "Checking port usage:"
        netstat -tlnp | grep :30000
        exit 1
    else
        echo "Attempt $i/10: Main server not ready, waiting..."
        sleep 60
    fi
done

# Additional connectivity tests
echo "Testing server connectivity..."
curl -v http://localhost:30000/v1/models 2>&1 | head -10
echo "Server process status:"
ps aux | grep -E "(sglang|python.*sglang)" | grep -v grep

# go into the submission directory 
cd $WORK/GitHub/crrrocq 

# launch pet-server with NUMA binding if available
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Launching pet-server..."
if [[ -n "$NUMA_CMD" ]]; then
    $NUMA_CMD pet-server > pet_server.log 2>&1 &
    PET_PID=$!
    
    # Verify pet-server is running and check its location
    sleep 5
    if ps -p $PET_PID > /dev/null; then
        echo "pet-server running on PID: $PET_PID"
        echo "Running on CPU: $(ps -o psr= -p $PET_PID)"
        echo "NUMA binding: $(numactl --show $PET_PID 2>/dev/null | grep -E 'nodebind|membind' || echo 'No explicit binding')"
    else
        echo "pet-server failed to start, check pet_server.log"
        cat pet_server.log
        exit 1
    fi
else
    pet-server > pet_server.log 2>&1 &
    PET_PID=$!
    echo "pet-server running on PID: $PET_PID (no NUMA binding)"
fi

# launch inference with NUMA binding if available
#echo "[$(date '+%Y-%m-%d %H:%M:%S')] Launching inference..."
#if [[ -n "$NUMA_CMD" ]]; then
#    $NUMA_CMD python -m src.inference.inference-cli --theorem $THM --file $FILE --workspace $WORKSPACE --model $MODEL
#else
#python -m src.inference.inference-cli --theorem $THM --file $FILE --workspace $WORKSPACE
#fi

# Keep the script running until the SLURM job times out
wait