# Simple Inference Pipeline

## Manual

Get resources:
```bash
$ srun --account=tdm@h100 --cpus-per-task=48 -C h100 --time=01:00:00 --gres=gpu:2 --qos=qos_gpu_h100-dev --pty bash
```

Then to launch the sglang server:
```bash
$ module load arch/h100 cuda/12.8.0

$ source /lustre/fswork/projects/rech/tdm/commun/venv/crrrocq/bin/activate

$ python -m sglang.launch_server --model-path /lustre/fsn1/projects/rech/tdm/commun/models/crrrocq_base/ --host 0.0.0.0 --base-gpu-id 1
```

Connect to your node with `srun` to launch the embedding server:
```bash
$ srun --jobid xxx --overlap --pty bash

$ source /lustre/fswork/projects/rech/tdm/commun/venv/crrrocq/bin/activate

$ python -m sglang.launch_server --model-path /lustre/fsn1/projects/rech/tdm/commun/hf_home/hub/models--Qwen--Qwen3-Embedding-4B/snapshots/5cf2132abc99cad020ac570b19d031efec650f2b --host 0.0.0.0 --port 31000 --is-embedding
```

Reconnect to your node with `srun` to launch the pet-server:
```bash
$ srun --jobid xxx --overlap --pty bash

$ pet-server
```

Reconnect to your node with `srun` to make experiment:
```bash
$ srun --jobid xxx --overlap --pty bash

$ source /lustre/fswork/projects/rech/tdm/commun/venv/crrrocq/bin/activate

$ cd where_is_crrrocq

$ python -m src.inference.inference-cli --theorem foo --file foo.v --workspace examples

$ python -m src.inference.inference-cli --theorem coef_prod_XsubC --file poly.v --workspace /lustre/fsn1/projects/rech/tdm/commun/math-comp/algebra --eval

```


## SLURM file is not working

Before you launch the job, you should perhaps modify line 49 with the location of your `crrrocq` repo, then:
```bash
$ sbatch inference.slurm
```

It will: 
- start a GPU with 2 nodes (H100) for 1h (you can add time up to 2h for more you should change the qos)
- lauch a sglang server with crrrocq on port 30000
- lauch a sglang server for the embedding model on port 31000
- lauch a pet-server
- once the crrrocq server is up, it run the inference for the theorem `foo` in the `examples/foo.v` file


Info below is not relevant anymore...
## Install

Set up a virtualenv with UV.

```bash
$ uv venv --python 3.11
$ source .venv/bin/activate
$ uv pip install vllm
```

## Usage

### Requirements
- Pet-server running
- vLLM server running (To be tested)

To run you need multiple terminal session in parallel.
In a terminal:
```bash
$ pet-server
```

In another:
```bash
$ vllm serve --tensor-parallel-size 4 --max-num-seqs 512 --gpu-memory-utilization 0.90 $DSDIR/HuggingFace_Models/Qwen/Qwen3-32B
```

### Running the CLI

```bash
# To prove a theorem using the real LLM:
python inference-cli.py --theorem foo --file foo.v --workspace examples --model $DSDIR/HuggingFace_Models/Qwen/Qwen3-32B

# To use the mock LLM for interactive testing:
python mock_inference.py --theorem foo --file foo.v --workspace examples --beam-size 2
```

### Running the pass@k
```bash
python pass_at_k_prover.py --theorem amc12_2000_p20 --file amc12_2000_p20.v --workspace examples --model /lustre/fsmisc/dataset/HuggingFace_Models/Qwen/Qwen3-32B --k 4 --verbose --context --llm-log-dir /lustre/fswork/projects/rech/tdm/uuz44ie/experiment-nlir/miniF2F/logs
```

### Running Tests

```bash
# Run specific test modules
python -m unittest test_parser.py
python -m unittest test_handler.py
python -m unittest test_agent.py
python -m unittest test_tools.py
```

## Project Structure

- `agent.py`: Contains the main agent implementation including Parser, ToolHandler, and MathProofAgent
- `tools.py`: Tool implementations (SearchTool, ScriptTool)
- `llm.py`: Language model interface and implementations
- `env.py`: Environment for interacting with Coq via Pytanque
- `inference-cli.py`: Command-line interface for running proofs
- `mock_inference.py`: Interactive testing with mock LLM

## Example Theorems

The repository includes example theorems in the `examples` directory:

- `foo.v`: Contains simple arithmetic theorems for testing
