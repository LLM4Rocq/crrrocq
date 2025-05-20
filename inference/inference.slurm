#!/bin/bash

#SBATCH --job-name=infer-test         # name of the job
#SBATCH --nodes=1                     # number of nodes
#SBATCH --ntasks-per-node=1           # number of MPI tasks per node
#SBATCH --hint=nomultithread          # reservation of physical cores (no hyperthreading)
#SBATCH --output=infer-test%j.out  # name of output file
#SBATCH --error=infer-test%j.err   # name of error file
#SBATCH --constraint=a100             # a100 gpus
#SBATCH --nodes=1                     # number of nodes
#SBATCH --gres=gpu:4                  # number of gpus/node
#SBATCH --time=04:00:00               # maximum execution time requested (HH:MM:SS)
#SBATCH --account=isf@a100            # account


MODEL=$DSDIR/HuggingFace_Models/Qwen/Qwen2.5-1.5B
WORKSPACE=examples
THM=amc12_2000_p20
LOGDIR=$WORK/logs


# clean out the modules loaded in interactive and inherited by default
module purge

# go into the submission directory 
cd $WORK/crrrocq 

# load uv env
source .venv/bin/activate

# go to the inference directory
cd inference

# launch vllm
vllm serve --tensor-parallel-size 4 --max-num-seqs 512 --gpu-memory-utilization 0.90 $DSDIR/HuggingFace_Models/Qwen/Qwen2.5-1.5B &

# poll the server until it's ready
sleep 30
until curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/v1/models | grep -q "200"; do
    echo "Waiting for server to respond..."
    sleep 5
done

# launch pet-server
pet-server &

# launch inference

python pass_at_k_prover.py --theorem $THM --file $THM.v --workspace $WORKSPACE --model $MODEL --k 32 --verbose --context --llm-log-dir $LOGDIR