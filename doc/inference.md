# Simple Inference Pipeline

## Code

To prove one theorem use `inference-cli.py` for a bench `benchmark.py`.
To modify the code:
- the main logic for the proof strategy is coded in the `process_with_tools` method of the `ToolHandler` in the `agent.py` file. Here you can modify the `active_prompt` that will be given to the LLM depending on the tool call.
- tools are defined in the `tools.py` file. For the script, the `ScriptEnv` is defined in the `env.py` file and is responsible for the interactions with the `pet-server`. In particular, there is a pb with some theorems with the `pet.start` cmd that should be modified here. For the moment, the have tool is treated as a script.
- interactions with the LLM are done through the `API_LLM` class in the `llm.py` file. The `build_prompt` methods there are not used anymore.



## Inference SLURM file: `inference2.slurm`

**Before you launch the job, you should modify line 159 with the location of your `crrrocq` repo.** Then:
```bash
$ sbatch inference2.slurm
```

It will: 
- start a GPU with 2 nodes (H100) for 1h (you can add time up to 2h for more you should change the qos)
- launch a sglang server with crrrocq on port 30000
- launch a sglang server for the embedding model on port 31000
- launch a pet-server
- once the crrrocq server is up, it runs the inference for the theorem `foo` in the `examples/foo.v` file.

If you want to prove another theorem you can launch:
```bash
$ sbatch --export=THM=coef_prod_XsubC,FILE=poly.v,WORKSPACE=/lustre/fsn1/projects/rech/tdm/commun/math-comp/algebra,NUM_ATTEMPT=16 inference2.slurm
```
**Warning!** once the inference is done for the theorem, the job continues so that you can do other inferences as follows:
```bash
$ srun --jobid xxx --overlap --pty bash
$ source /lustre/fswork/projects/rech/tdm/commun/venv/crrrocq/bin/activate
$ cd where your crrrocq repo is
$ python -m src.inference.inference-cli --theorem coef_prod_XsubC --file poly.v --workspace /lustre/fsn1/projects/rech/tdm/commun/math-comp/algebra --eval
```
By default, all logs are stored in `llm_logs` in your `crrrocq` repo.

I do not understand why the `inference.slurm` file is not working...

## Bench SLURM files

Probably not useful anymore see the `inference` branch. 

The files `bench.slurm` and `bench_qos.slurm` are using 2xH100 and one is used for the main server and the other for the embedding server. The only difference is the QOS `bench_qos.slurm` is limited to 2 hours but has a high priority.

The file `bench_fullnode.slurm` uses 4xH100 and split the main server on the 4 GPUs and the embedding server on 2 GPUs (high priority, if you want to run for more than 2 hours, you should remove the `--qos`).

The files are launching the `benchmark.py` file. First theorems and corresponding files are retrieved from the keys of the json file `/lustre/fsn1/projects/rech/tdm/commun/dataset/evaluation.json`. There are quite a few errors due to the problem with the start method of the `pet-server` (or bad parsing of the keys or both?). The new arguments are:
- `max_workers`: number of // threads
- `num_attempt`: number of attempts for a script
- `num_full_attempt`: number of proof attempts per theorem.

In the `bench_fullnode.slurm` the default logging directory is on my `$SCRATH`, this will probably make an error for you so you should modify this line.

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
