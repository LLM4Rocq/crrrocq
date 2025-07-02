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


# clean out the modules loaded in interactive and inherited by default
module purge
pkill pet-server
pkill vllm

# load the nsight module
module load nvidia-nsight-systems/2024.7.1.84

# echo commands
set -x

# do not store tmp files in /tmp!
export TMPDIR=$JOBSCRATCH

# nsight bug
ln -s $JOBSCRATCH /tmp/nvidia

MODEL=$DSDIR/HuggingFace_Models/Qwen/Qwen2.5-1.5B
WORKSPACE=examples
THM=amc12_2000_p20
LOGDIR=$WORK/logs

# go into the submission directory 
cd $WORK/crrrocq 

# load uv env
source .venv/bin/activate

# go to the inference directory
cd inference

# launch vllm
vllm serve --tensor-parallel-size 4 --max-num-seqs 512 --gpu-memory-utilization 0.90 $MODEL &

# poll the server until it's ready
sleep 300
until curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/v1/models | grep -q "200"; do
    echo "Waiting for server to respond..."
    sleep 5
done

# launch pet-server
pet-server &

# launch inference

python pass_at_k_prover.py --theorem $THM --file $THM.v --workspace $WORKSPACE --model $MODEL --k 8 --max-iterations 2 --verbose --context --llm-log-dir $LOGDIR

pkill vllm
pkill pet-server