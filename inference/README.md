# Simple Inference Pipeline

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
python mock_inference.py --theorem foo --file foo.v --workspace examples
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
- `tools.py`: Tool implementations (SearchTool, CoqProverTool)
- `llm.py`: Language model interface and implementations
- `env.py`: Environment for interacting with Coq via Pytanque
- `inference-cli.py`: Command-line interface for running proofs
- `mock_inference.py`: Interactive testing with mock LLM

## Example Theorems

The repository includes example theorems in the `examples` directory:

- `foo.v`: Contains simple arithmetic theorems for testing
