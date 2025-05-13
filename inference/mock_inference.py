import os
import sys
import argparse
from pytanque import Pytanque
from tools import SearchTool, CoqProverTool
from agent import MathProofAgent
from mock_llm import MockVLLM


def main():
    """Main entry point for the mock inference CLI."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Coq Proof Assistant CLI with Mock LLM"
    )
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
        "--beam-size",
        type=int,
        default=1,
        help="Number of parallel paths to explore (beam search width)",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    # Setup Pytanque
    pet = Pytanque(args.host, args.port)
    pet.connect()
    pet.set_workspace(False, str(args.workspace))

    # Setup tools
    search_tool = SearchTool()
    coq_tool = CoqProverTool(
        pet=pet,
        workspace=args.workspace,
        file=args.file,
        theorem=args.theorem,
    )

    # Setup Mock LLM
    llm = MockVLLM()

    # Print instructions for the user
    print("\nMock LLM Server Activated")
    print(
        "You will see the prompts sent to the LLM and can provide responses manually."
    )
    print("When entering a response, type 'END' on a new line to finish.\n")

    if args.beam_size > 1:
        print(f"Using beam search with {args.beam_size} beams.")
        print("You'll be prompted for completions for each active beam.")

    # Create agent and run proof
    agent = MathProofAgent(llm, search_tool, coq_tool)
    status = agent.run_proof(beam_size=args.beam_size, verbose=args.verbose)

    # Print results
    if status.success:
        print("\nProof completed successfully!")
    else:
        print("\nProof incomplete.")

    print("\nProof tactics:")
    for tactic in status.proof:
        print(f"  {tactic}")


if __name__ == "__main__":
    main()
