#!/bin/bash

#SBATCH --job-name=infer-test         # name of the job
#SBATCH --nodes=1                     # number of nodes
#SBATCH --ntasks-per-node=1           # number of MPI tasks per node
#SBATCH --hint=nomultithread          # reservation of physical cores (no hyperthreading)
#SBATCH --output=infer-test%j.out  # name of output file
#SBATCH --error=infer-test%j.err   # name of error file
#SBATCH --constraint=h100             # h100 gpus
#SBATCH --nodes=1                     # number of nodes
#SBATCH --gres=gpu:2                  # number of gpus/node
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
WORKSPACE=${WORKSPACE:-examples}
THM=${THM:-foo}
FILE=${FILE:-foo.v}
PORT_EMB=31000
NUM_ATTEMPT=${NUM_ATTEMPT:-32}
MAX_ITERATIONS=100
LOG_DIR=${LOG_DIR:-llm_logs}

python -m sglang.launch_server --model-path $MODEL --tp-size 2 --mem-fraction-static 0.7 --host 0.0.0.0 &
python -m sglang.launch_server --model-path $MODEL_EMB --base-gpu-id 1 --mem-fraction-static 0.29 --host 0.0.0.0 --port $PORT_EMB --is-embedding &

until curl -s -o /dev/null -w "%{http_code}" http://localhost:30000/v1/models | grep -q "200"; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Waiting for server to respond..."
    sleep 60
done

# go into the submission directory 
cd $WORK/GitHub/crrrocq 

# Run pet-server 
pet-server &

# launch inference 
python -m src.inference.inference-cli --theorem $THM --file $FILE --workspace $WORKSPACE \
        --num-attempt $NUM_ATTEMPT \
        --max-iterations $MAX_ITERATIONS \
        --log-dir $LOG_DIR

# Keep the script running until the SLURM job times out

wait