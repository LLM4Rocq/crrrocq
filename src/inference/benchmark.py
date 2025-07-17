import argparse
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional
import time
from dataclasses import dataclass

from pytanque import Pytanque
from .tools import SearchTool, ScriptTool, HaveTool
from .llm import VLLM
from .agent import MathProofAgent, Status
from .utils import extract_proof, get_proof_tactics, get_evaluation_theorems

# from src.embedding.models.qwen_embedding import Qwen3Embedding4b
# from src.embedding.index.cosim_index import FaissIndex


@dataclass
class BenchmarkResult:
    """Result of a theorem proving attempt."""

    theorem_name: str
    full_name: str
    workspace_path: str
    file_name: str
    success: bool
    proof_tactics: List[str]
    error_message: Optional[str] = None
    execution_time: float = 0.0


def prove_single_theorem(theorem_info: Dict[str, str], args) -> BenchmarkResult:
    """
    Prove a single theorem synchronously.

    Args:
        theorem_info: Dictionary containing theorem information from get_evaluation_theorems
        args: Command line arguments with configuration

    Returns:
        BenchmarkResult with the proof attempt result
    """
    start_time = time.time()

    try:
        # Setup Pytanque for this theorem
        pet = Pytanque(args.host, args.port)
        pet.connect()
        pet.set_workspace(False, theorem_info["workspace_path"])

        # Setup tools
        search_tool = SearchTool(
            index_path=args.index_cache_path,
            model=args.model_embedding,
            api_url=args.embedding_api,
            docstrings_path=args.docstrings_path,
        )

        script_tool = ScriptTool(
            pet=pet,
            workspace=theorem_info["workspace_path"],
            file=theorem_info["file_name"],
            theorem=theorem_info["lemma_name"],
        )

        have_tool = HaveTool(
            pet=pet,
            workspace=theorem_info["workspace_path"],
            file=theorem_info["file_name"],
            theorem=theorem_info["lemma_name"],
        )

        # Setup LLM
        llm = VLLM(
            api_url=args.llm_url,
            model=args.model,
            temperature=args.temperature,
            verbose=args.verbose,
        )

        # Create agent and run proof
        agent = MathProofAgent(llm, search_tool, script_tool, have_tool)
        status = agent.run_proof(beam_size=args.beam_size, verbose=args.verbose)

        execution_time = time.time() - start_time

        return BenchmarkResult(
            theorem_name=theorem_info["lemma_name"],
            full_name=theorem_info["full_name"],
            workspace_path=theorem_info["workspace_path"],
            file_name=theorem_info["file_name"],
            success=status.success,
            proof_tactics=status.proof,
            execution_time=execution_time,
        )

    except Exception as e:
        execution_time = time.time() - start_time
        return BenchmarkResult(
            theorem_name=theorem_info["lemma_name"],
            full_name=theorem_info["full_name"],
            workspace_path=theorem_info["workspace_path"],
            file_name=theorem_info["file_name"],
            success=False,
            proof_tactics=[],
            error_message=str(e),
            execution_time=execution_time,
        )


async def run_benchmark_async(
    theorems: List[Dict[str, str]],
    args,
    max_workers: int = 4,
    max_theorems: Optional[int] = None,
) -> List[BenchmarkResult]:
    """
    Run theorem proving benchmark asynchronously on multiple theorems.

    Args:
        theorems: List of theorem information dictionaries
        args: Command line arguments with configuration
        max_workers: Maximum number of concurrent workers
        max_theorems: Maximum number of theorems to process (None for all)

    Returns:
        List of BenchmarkResult objects
    """
    # Limit theorems if specified
    if max_theorems is not None:
        theorems = theorems[:max_theorems]

    print(f"Starting benchmark on {len(theorems)} theorems with {max_workers} workers")

    # Create event loop and thread pool
    loop = asyncio.get_event_loop()
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        futures = [
            loop.run_in_executor(executor, prove_single_theorem, theorem, args)
            for theorem in theorems
        ]

        # Collect results as they complete
        for i, future in enumerate(asyncio.as_completed(futures)):
            result = await future
            results.append(result)

            # Progress reporting
            print(
                f"[{i+1}/{len(theorems)}] {result.theorem_name}: "
                f"{'SUCCESS' if result.success else 'FAILED'} "
                f"({result.execution_time:.2f}s)"
            )

            if result.error_message:
                print(f"  Error: {result.error_message}")

    return results


def print_benchmark_summary(results: List[BenchmarkResult]):
    """Print a summary of benchmark results."""
    total = len(results)
    successful = sum(1 for r in results if r.success)
    failed = total - successful

    total_time = sum(r.execution_time for r in results)
    avg_time = total_time / total if total > 0 else 0

    print(f"\n=== BENCHMARK SUMMARY ===")
    print(f"Total theorems: {total}")
    print(f"Successful: {successful} ({successful/total*100:.1f}%)")
    print(f"Failed: {failed} ({failed/total*100:.1f}%)")
    print(f"Total time: {total_time:.2f}s")
    print(f"Average time per theorem: {avg_time:.2f}s")

    if failed > 0:
        print(f"\nFailed theorems:")
        for result in results:
            if not result.success:
                print(f"  - {result.theorem_name} ({result.file_name})")
                if result.error_message:
                    print(f"    Error: {result.error_message}")


def save_benchmark_results(results: List[BenchmarkResult], output_path: str):
    """Save benchmark results to JSON file."""
    results_data = []
    for result in results:
        results_data.append(
            {
                "theorem_name": result.theorem_name,
                "full_name": result.full_name,
                "workspace_path": result.workspace_path,
                "file_name": result.file_name,
                "success": result.success,
                "proof_tactics": result.proof_tactics,
                "error_message": result.error_message,
                "execution_time": result.execution_time,
            }
        )

    with open(output_path, "w") as f:
        json.dump(results_data, f, indent=2)

    print(f"Results saved to {output_path}")


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
        "--llm-url", type=str, default="http://localhost:30000", help="LLM API URL"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="/lustre/fsn1/projects/rech/tdm/commun/models/crrrocq_base/",
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
        default=0.6,
        help="Temperature for the LLM generation",
    )

    parser.add_argument(
        "--docstrings-path",
        default="/lustre/fsn1/projects/rech/tdm/commun/dataset/docstrings.json",
        help="Docstrings path",
    )
    parser.add_argument(
        "--index-cache-path",
        default="/lustre/fsn1/projects/rech/tdm/commun/cache/index",
        help="Index cache path",
    )

    parser.add_argument(
        "--model-embedding",
        default="/lustre/fsn1/projects/rech/tdm/commun/hf_home/hub/models--Qwen--Qwen3-Embedding-4B/snapshots/5cf2132abc99cad020ac570b19d031efec650f2b",
        help="Model for embedding",
    )

    parser.add_argument(
        "--embedding-api",
        default="http://localhost:31000",
        help="API URL for embedding service",
    )

    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    parser.add_argument("--check", action="store_true", help="Check proof is valid")

    # New benchmark arguments
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Run benchmark on all theorems from evaluation.json",
    )

    parser.add_argument(
        "--evaluation-json",
        type=str,
        default="/lustre/fsn1/projects/rech/tdm/commun/dataset/evaluation.json",
        help="Path to evaluation.json file",
    )

    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Maximum number of concurrent workers for benchmark",
    )

    parser.add_argument(
        "--max-theorems",
        type=int,
        default=None,
        help="Maximum number of theorems to process (None for all)",
    )

    parser.add_argument(
        "--output-file",
        type=str,
        default="benchmark_results.json",
        help="Output file for benchmark results",
    )

    args = parser.parse_args()

    # Handle benchmark mode
    if args.benchmark:
        # Load theorems from evaluation.json
        theorems = get_evaluation_theorems(args.evaluation_json)

        if not theorems:
            print("No theorems found in evaluation.json. Exiting.")
            return

        print(f"Found {len(theorems)} theorems for benchmarking")

        # Run benchmark asynchronously
        results = asyncio.run(
            run_benchmark_async(
                theorems,
                args,
                max_workers=args.max_workers,
                max_theorems=args.max_theorems,
            )
        )

        # Print and save results
        print_benchmark_summary(results)
        save_benchmark_results(results, args.output_file)
        return

    # Setup Pytanque for single theorem mode
    pet = Pytanque(args.host, args.port)
    pet.connect()
    pet.set_workspace(False, str(args.workspace))

    # Setup tools
    # embedding_model = Qwen3Embedding4b(args.embedding_device)

    search_tool = SearchTool(
        index_path=args.index_cache_path,
        model=args.model_embedding,
        api_url=args.embedding_api,
        docstrings_path=args.docstrings_path,
    )

    script_tool = ScriptTool(
        pet=pet,
        workspace=args.workspace,
        file=args.file,
        theorem=args.theorem,
    )

    if args.check:
        try:
            file_path = "/lustre/fsn1/projects/rech/tdm/commun/dataset/evaluation.json"
            with open(file_path, "r", encoding="utf-8") as file:
                json_data = json.load(file)

            print(f"Loaded JSON data with {len(json_data)} proofs")

            statement_name = args.theorem
            print(f"\n=== Extracting proof for: {statement_name} ===")

            proof = extract_proof(json_data, statement_name)

            if proof:
                print("\nTactics used:")
                tactics = get_proof_tactics(proof)
                for tactic in tactics:
                    if tactic:  # Only show non-empty tactics
                        print(f"  - {tactic}")
                        checking_proof = script_tool.run(tactic)
            else:
                print("Proof not found")

            print(f"Proof checking status: {checking_proof}")
            del script_tool

        except FileNotFoundError:
            print(f"Error: File '{file_path}' not found. Please check the file path.")

        except json.JSONDecodeError as e:
            print(f"Error parsing JSON file: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")

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
