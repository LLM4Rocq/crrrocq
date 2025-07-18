import argparse
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional, Tuple
import time
from dataclasses import dataclass

from pytanque import Pytanque
from .tools import SearchTool, ScriptTool, HaveTool, ThreadLocalSearchTool
from .llm import VLLM, ThreadLocalVLLM
from .agent import MathProofAgent, Status
from .utils import (
    extract_proof,
    get_proof_tactics,
    get_evaluation_theorems,
    get_parsed_statements,
)

# from src.embedding.models.qwen_embedding import Qwen3Embedding4b
# from src.embedding.index.cosim_index import FaissIndex


def run_single_proof_with_mixed_tools(
    shared_llm: ThreadLocalVLLM,
    shared_search_tool: ThreadLocalSearchTool,
    theorem: str,
    theorem_file: str,
    theorem_id: int,
    tool_configs: Dict[str, Dict[str, Any]],
    beam_size: int = 1,
    verbose: bool = False,
    **agent_kwargs,
) -> Dict[str, Any]:
    """
    Run a single proof with mixed tool sharing strategy:
    - LLM: Thread-local (shared)
    - SearchTool: Thread-local (shared)
    - Other tools: Fresh instances per thread
    """
    thread_name = threading.current_thread().name
    print(f"Theorem {theorem_id}: Starting proof on thread {thread_name}")

    try:
        # Use shared thread-local SearchTool
        search_tool = shared_search_tool

        # Setup Pytanque
        pet_config = tool_configs["pet"]
        pet = Pytanque(pet_config.host, pet_config.port)
        pet.connect()
        pet.set_workspace(False, str(pet_config.workspace))

        # Create fresh instances for other tools (if not thread-safe)
        # script_config = tool_configs["script"]
        script_tool = ScriptTool(
            pet=pet,
            workspace=pet_config.workspace,
            file=theorem_file,
            theorem=theorem,
        )

        have_tool = HaveTool(
            pet=pet,
            workspace=pet_config.workspace,
            file=theorem_file,
            theorem=theorem,
        )

        # Create MathProofAgent with mixed tool strategy
        agent = MathProofAgent(
            llm=shared_llm,  # Thread-local LLM (shared)
            search_tool=search_tool,  # Thread-local SearchTool (shared)
            script_tool=script_tool,  # Fresh instance (thread-safe)
            have_tool=have_tool,  # Fresh instance (thread-safe)
        )

        # Run the proof
        status = agent.run_proof(beam_size=beam_size, verbose=verbose)

        print(f"Theorem {theorem_id}: Completed with status {status}")

        return {
            "theorem_id": theorem_id,
            "theorem": theorem,
            "status": status,
            "success": status.success,
            "thread": thread_name,
            "tools_strategy": {
                "llm": "thread_local",
                "search": "thread_local",
                "script": "fresh_instance",
                "have": "fresh_instance",
            },
        }

    except Exception as e:
        print(f"Theorem {theorem_id}: Failed with error: {e}")
        return {
            "theorem_id": theorem_id,
            "theorem": theorem,
            "status": "error",
            "success": False,
            "error": str(e),
            "thread": thread_name,
        }


def run_parallel_proofs_with_mixed_tools(
    theorems: List[str],
    shared_llm: ThreadLocalVLLM,
    shared_search_tool: ThreadLocalSearchTool,
    tool_configs: Dict[str, Dict[str, Any]],
    max_workers: int = 4,
    beam_size: int = 1,
    verbose: bool = False,
    **agent_kwargs,
) -> List[Dict[str, Any]]:
    """
    Run multiple proofs in parallel with mixed tool sharing strategy.

    Args:
        theorems: List of theorems to prove
        shared_llm: ThreadLocalVLLM instance
        shared_search_tool: ThreadLocalSearchTool instance
        tool_configs: Configuration for other tools (script, have)
        max_workers: Maximum number of concurrent threads
        **agent_kwargs: Additional arguments for MathProofAgent

    Returns:
        List of proof results
    """
    print(
        f"Starting parallel proof of {len(theorems)} theorems with {max_workers} workers"
    )
    print(f"Using thread-local LLM and SearchTool, fresh instances for other tools")

    results = []

    # Make a copy of tool_configs for each thread
    def get_tool_configs_copy():
        return {tool_type: config.copy() for tool_type, config in tool_configs.items()}

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all proof tasks
        future_to_theorem = {
            executor.submit(
                run_single_proof_with_mixed_tools,
                shared_llm,
                shared_search_tool,
                theorem,
                theorem_file,
                theorem_id,
                get_tool_configs_copy(),
                **agent_kwargs,
            ): theorem_id
            for theorem_id, (theorem, theorem_file) in enumerate(theorems)
        }

        # Collect results as they complete
        for future in concurrent.futures.as_completed(future_to_theorem):
            theorem_id = future_to_theorem[future]
            try:
                result = future.result()
                results.append(result)

                # Log progress
                success_count = sum(1 for r in results if r["success"])
                print(
                    f"Progress: {len(results)}/{len(theorems)} completed, {success_count} successful"
                )

            except Exception as e:
                print(f"Theorem {theorem_id}: Unexpected error: {e}")
                results.append(
                    {
                        "theorem_id": theorem_id,
                        "theorem": theorems[theorem_id],
                        "status": "unexpected_error",
                        "success": False,
                        "error": str(e),
                    }
                )

    # Sort results by theorem_id to maintain order
    results.sort(key=lambda x: x["theorem_id"])

    return results


def get_theorems(file_path: str) -> List[Tuple[str, str]]:
    with open(file_path, "r", encoding="utf-8") as file:
        json_data = json.load(file)

    print(f"Loaded JSON data with {len(json_data)} proofs")
    theorems = []

    parsed_statements = get_parsed_statements(json_data)

    for stmt_info in parsed_statements:
        theorems.append(
            (
                stmt_info["lemma_name"],
                f"{stmt_info['folder_name']}/{stmt_info['file_name']}",
            )
        )
    return theorems


def main():
    """Main entry point for the inference CLI."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Coq Proof Assistant CLI")
    parser.add_argument(
        "--workspace",
        type=str,
        default="/lustre/fsn1/projects/rech/tdm/commun/math-comp",
        help="Path to the workspace directory",
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

    # Initialize thread-local LLM
    shared_llm = ThreadLocalVLLM(
        api_url=args.llm_url,
        model=args.model,
        temperature=args.temperature,
        verbose=args.verbose,
    )

    # Initialize thread-local SearchTool
    shared_search_tool = ThreadLocalSearchTool(
        index_path=args.index_cache_path,
        model=args.model_embedding,
        api_url=args.embedding_api,
        docstrings_path=args.docstrings_path,
    )

    # Configure other tools (only script and have now)
    tool_configs = {
        "pet": {
            "host": args.host,
            "port": args.port,
            "workspace": str(args.workspace),
        },
    }

    theorems = get_theorems(args.evaluation_json)
    theorems = theorems[: args.max_theorems] if args.max_theorems else theorems

    # Run parallel proofs
    results = run_parallel_proofs_with_mixed_tools(
        theorems=theorems,
        shared_llm=shared_llm,
        shared_search_tool=shared_search_tool,
        tool_configs=tool_configs,
        max_workers=4,
    )

    # Show results
    print(f"\n=== Results ===")
    print(f"Total VLLM instances: {shared_llm.instance_count}")
    print(f"Total SearchTool instances: {shared_search_tool.instance_count}")

    success_count = sum(1 for r in results if r["success"])
    print(f"Successful proofs: {success_count}/{len(results)}")


if __name__ == "__main__":
    main()
