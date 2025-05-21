import os
import sys
import argparse
from typing import List, Optional, Tuple, Dict, Any

from prover_agent import CoqProofManager, ProverResult
from tools import CoqProverTool
from llm import VLLM
from pytanque import Pytanque


class PassAtKProver:
    """
    Implements pass@k algorithm for theorem proving using CoqProofManager and VLLM.
    """

    def __init__(
        self,
        llm: VLLM,
        coq_tool: CoqProverTool,
        k: int = 3,
        max_iterations: int = 10,
        verbose: bool = False,
        goals_tag: str = "GOALS",
        result_tag: str = "r",
    ):
        """
        Initialize the pass@k prover.

        Args:
            llm: VLLM instance for generating completions
            coq_tool: CoqProverTool instance for theorem proving
            k: Number of parallel paths to explore
            max_iterations: Maximum number of iterations before giving up
            verbose: Whether to print verbose output
            goals_tag: The XML tag to use for goals (default: "GOALS")
            result_tag: The tag to use for result output (default: "r")
        """
        self.llm = llm
        self.proof_manager = CoqProofManager(coq_tool)
        self.k = k
        self.max_iterations = max_iterations
        self.verbose = verbose
        self.goals_tag = goals_tag
        self.result_tag = result_tag
        self.context = coq_tool.env.context

    def run_pass_at_k(self) -> Tuple[bool, List[str]]:
        """
        Run pass@k algorithm to find a proof.

        Returns:
            Tuple of (success flag, proof steps)
        """
        if self.verbose:
            print(f"Starting pass@k with k={self.k}")

        # Get initial state from the proof manager
        coq_tools, tool_tag = self.proof_manager.get_initial_state(self.k)

        # Get stop sequences for the LLM
        stop_sequences = self.proof_manager.get_stop_sequences()

        # Create initial prompts for each path
        prompts = [
            self.llm.build_prompt(
                tool.env.thm_code, tool.tag, self.context, self.goals_tag
            )
            for tool in coq_tools
        ]

        # Main pass@k loop
        for iteration in range(self.max_iterations):
            if self.verbose:
                print(f"\nIteration {iteration+1}/{self.max_iterations}")

            # Generate responses for all paths
            responses = self.llm.generate_batch(prompts, stop_sequences)

            if self.verbose:
                for i, response in enumerate(responses):
                    print(f"Path {i} response: {response[:100]}...")

            # Process the batch of responses
            results, successful_result = self.proof_manager.process_batch_responses(
                responses=responses, coq_tools=coq_tools, verbose=self.verbose
            )

            # If any path completed the proof
            if successful_result:
                if self.verbose:
                    print(f"Found successful proof!")
                return True, successful_result.proof

            # Update prompts for paths that made progress
            for i, result in enumerate(results):
                if not result.is_complete:  # and result.success:
                    # Add the response and new goals to the conversation
                    prompts[i] += self.llm.build_prompt_with_feedback(
                        goals=result.new_goals,
                        coq_tag=tool_tag,
                        response=responses[i],
                        # added_tac=result.added_tac,
                        success=result.success,
                        current_proof=result.proof,
                        previous_attempts=result.previous_unsuccessful,
                        context=self.context,
                        goals_tag=self.goals_tag,
                    )
                    # += (
                    #    f"\n<{self.result_tag}>\n{result.proof}\n</{self.result_tag}>\n"
                    #    + responses[i]
                    #    + f"\n<{self.goals_tag}>\n{result.new_goals}\n</{self.goals_tag}>\n"
                    # )
                    if self.verbose:
                        print(f"Path {i} made progress, updating prompt.")
                        print(f"current proof: {result.proof}")
                        print(f"previous attempts: {result.previous_unsuccessful}")
                # Otherwise, keep the same prompt for this path (retry)

            if self.verbose:
                print(f"No path completed the proof in iteration {iteration+1}.")

        # If we've reached the maximum iterations without finding a proof
        if self.verbose:
            print(f"Reached maximum iterations ({self.max_iterations}). Search failed.")
        return False, []


def main():
    """Main entry point for the pass@k prover CLI."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Pass@k Coq Prover")
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
        "--k",
        type=int,
        default=3,
        help="Number of parallel paths to explore (pass@k parameter)",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=10,
        help="Maximum number of iterations before giving up",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="Temperature for the LLM generation (higher values increase diversity)",
    )
    parser.add_argument(
        "--goals-tag", type=str, default="GOALS", help="XML tag to use for goals"
    )
    parser.add_argument(
        "--result-tag", type=str, default="SCRIPT", help="Tag to use for result output"
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument(
        "--context", action="store_true", help="Include context in prompts"
    )

    # Add logging argument
    parser.add_argument(
        "--llm-log-dir",
        type=str,
        default="llm_logs",
        help="Directory to store LLM interaction logs",
    )

    args = parser.parse_args()

    # Setup Pytanque
    pet = Pytanque(args.host, args.port)
    pet.connect()
    pet.set_workspace(False, str(args.workspace))

    # Setup CoqProverTool
    coq_tool = CoqProverTool(
        pet=pet,
        workspace=args.workspace,
        file=args.file,
        theorem=args.theorem,
        context=args.context,
    )

    # Setup LLM
    llm = VLLM(
        api_url=args.llm_url,
        model=args.model,
        temperature=args.temperature,
        verbose=args.verbose,
        log_dir=args.llm_log_dir,
        log_to_console=args.verbose,
    )

    # Create and run the pass@k prover
    prover = PassAtKProver(
        llm=llm,
        coq_tool=coq_tool,
        k=args.k,
        max_iterations=args.max_iterations,
        verbose=args.verbose,
        goals_tag=args.goals_tag,
        result_tag=args.result_tag,
    )

    success, proof = prover.run_pass_at_k()

    # Print results
    if success:
        print("\nProof completed successfully!")
        print("\nProof tactics:")
        for tactic in proof:
            print(f"  {tactic}")
    else:
        print("\nProof incomplete.")
        print("Hint: Try increasing k, max iterations, or temperature.")


if __name__ == "__main__":
    main()
