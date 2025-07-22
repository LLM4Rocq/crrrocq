import argparse
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional, Tuple
import time
from dataclasses import dataclass
import threading
import concurrent.futures

from pytanque import Pytanque
from .tools import SearchTool, ScriptTool, HaveTool
from .llm import API_LLM
from .agent import MathProofAgent, Status
from .utils import (
    extract_proof,
    get_proof_tactics,
    get_evaluation_theorems,
    get_parsed_statements,
    make_session_name,
)


def run_single_proof(
    theorem: str,
    theorem_file: str,
    theorem_id: int,
    tool_configs: Dict[str, Dict[str, Any]],
    num_attempt: int = 1,
    max_iterations: int = 100,
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

        search_config = tool_configs["search"]
        search_tool = SearchTool(
            index_path=search_config["index_path"],
            model=search_config["model"],
            api_url=search_config["api_url"],
            docstrings_path=search_config["docstrings_path"],
        )

        # Setup Pytanque
        pet_config = tool_configs["pet"]
        pet = Pytanque(pet_config["host"], pet_config["port"])
        pet.connect()
        pet.set_workspace(False, str(pet_config["workspace"]))

        script_tool = ScriptTool(
            pet=pet,
            workspace=pet_config["workspace"],
            file=theorem_file,
            theorem=theorem,
        )

        have_tool = HaveTool(
            pet=pet,
            workspace=pet_config["workspace"],
            file=theorem_file,
            theorem=theorem,
        )

        # Set the session name for this theorem
        theorem_session_name = f"{theorem_file[:-2]}_{theorem}_{theorem_id}"

        llm_config = tool_configs["llm"]
        llm = API_LLM(
            api_url=llm_config["api_url"],
            model=llm_config["model"],
            temperature=llm_config["temperature"],
            verbose=llm_config["verbose"],
            log_dir=llm_config["log_dir"],
            session_name=make_session_name(theorem_session_name),
        )

        agent = MathProofAgent(
            llm=llm,
            search_tool=search_tool,
            script_tool=script_tool,
            have_tool=have_tool,
        )

        status = agent.run_proof(
            num_attempt=num_attempt,
            max_iterations=max_iterations,
            verbose=verbose,
        )

        print(f"Theorem {theorem_id}: Completed with status {status}")

        return {
            "theorem_id": theorem_id,
            "theorem": theorem,
            "status": status,
            "success": status.success,
            "thread": thread_name,
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


def run_parallel_proofs(
    theorems: List[str],
    tool_configs: Dict[str, Dict[str, Any]],
    max_workers: int = 4,
    num_attempt: int = 1,
    max_iterations: int = 100,
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
                run_single_proof,
                theorem,
                theorem_file,
                theorem_id,
                get_tool_configs_copy(),
                num_attempt,
                max_iterations,
                verbose,
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
        "--num-attempt",
        type=int,
        default=8,
        help="Number of attempts to prove each theorem",
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        default=100,
        help="Maximum number of iterations for each proof attempt",
    )

    parser.add_argument(
        "--log-dir",
        type=str,
        default="bench_logs",
        help="Directory to store logs",
    )

    args = parser.parse_args()

    # Configure other tools (only script and have now)
    tool_configs = {
        "pet": {
            "host": args.host,
            "port": args.port,
            "workspace": str(args.workspace),
        },
        "llm": {
            "api_url": args.llm_url,
            "model": args.model,
            "temperature": args.temperature,
            "verbose": args.verbose,
            "log_dir": args.log_dir,
        },
        "search": {
            "index_path": args.index_cache_path,
            "model": args.model_embedding,
            "api_url": args.embedding_api,
            "docstrings_path": args.docstrings_path,
        },
    }

    theorems = get_theorems(args.evaluation_json)
    theorems = theorems[: args.max_theorems] if args.max_theorems else theorems

    # Run parallel proofs
    results = run_parallel_proofs(
        theorems=theorems,
        tool_configs=tool_configs,
        max_workers=args.max_workers,
        num_attempt=args.num_attempt,
        max_iterations=args.max_iterations,
    )

    # Show results
    print(f"\n=== Results ===")
    success_count = sum(1 for r in results if r["success"])
    print(f"Successful proofs: {success_count}/{len(results)}")

    output_file_path = os.path.join(args.log_dir, "benchmark_results.json")
    try:
        with open(output_file_path, "w", encoding="utf-8") as output_file:
            json.dump(results, output_file, indent=2, ensure_ascii=False)
        print(f"Results saved to {output_file_path}")
    except Exception as e:
        print(f"Failed to save results to {output_file_path}: {e}")


if __name__ == "__main__":
    main()
