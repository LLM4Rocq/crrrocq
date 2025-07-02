import os
import sys
import argparse
from pytanque import Pytanque
from tools import SearchTool, ScriptTool, HaveTool
from llm import VLLM
from agent import MathProofAgent


def main():
    """Main entry point for the inference CLI."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Coq Proof Assistant CLI")
    parser.add_argument(
        "--workspace",
        type=str,
        default="examples",
        help="Path to the workspace directory",
    )
    parser.add_argument("--file", type=str, default="foo.v", help="Coq file name")
    parser.add_argument(
        "--theorem", type=str, required=True, help="Name of the theorem to prove"
    )
    parser.add_argument(
        "--host", type=str, default="127.0.0.1", help="Pytanque server host"
    )
    parser.add_argument("--port", type=int, default=8765, help="Pytanque server port")
    parser.add_argument(
        "--llm-url", type=str, default="http://localhost:8000", help="LLM API URL"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B",
        help="LLM model name",
    )
    parser.add_argument(
        "--beam-size",
        type=int,
        default=1,
        help="Number of parallel paths to explore (beam search width)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.1,
        help="Temperature for the LLM generation",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    # Setup Pytanque
    pet = Pytanque(args.host, args.port)
    pet.connect()
    pet.set_workspace(False, str(args.workspace))

    # Setup tools
    search_tool = SearchTool()
    script_tool = ScriptTool(
        pet=pet,
        workspace=args.workspace,
        file=args.file,
        theorem=args.theorem,
    )
    have_tool = HaveTool(
        pet=pet,
        workspace=args.workspace,
        file=args.file,
        theorem=args.theorem,
    )

    # Setup LLM
    llm = VLLM(
        api_url=args.llm_url,
        model=args.model,
        temperature=args.temperature,
        verbose=args.verbose,
    )

    # Create agent and run proof with specified beam size
    agent = MathProofAgent(llm, search_tool, script_tool, have_tool)
    status = agent.run_proof(beam_size=args.beam_size, verbose=args.verbose)

    # Print results
    if status.success:
        print("Proof completed successfully!")
    else:
        print("Proof incomplete.")

    print("\nProof tactics:")
    for tactic in status.proof:
        print(f"  {tactic}")


if __name__ == "__main__":
    main()
