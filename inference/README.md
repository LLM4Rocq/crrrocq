# Simple Inference Pipeline


## Usage

### Requirements
- Pet-server running
- vLLM server running (To be tested)
```bash
VLLM_USE_CUDA=0 python -m vllm.entrypoints.api_server \
    --model deepseek-ai/DeepSeek-R1-Distill-Qwen-7B \
    --tensor-parallel-size 1 \
    --host 0.0.0.0 \
    --port 8000 \
    --max-model-len 74000 
```

### Running the CLI

```bash
# To prove a theorem using the real LLM:
python inference-cli.py --theorem foo --file foo.v --workspace examples

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
