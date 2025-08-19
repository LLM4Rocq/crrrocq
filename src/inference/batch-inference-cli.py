import argparse
import yaml
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Tuple
import threading
from dataclasses import dataclass

from pytanque import Pytanque
from .tools import SearchTool, ScriptTool, HaveTool
from .llm import API_LLM
from .agent import MathProofAgent
from .utils import extract_proof, get_proof_tactics, make_session_name


@dataclass
class TheoremTask:
    """Represents a single theorem proving task"""
    file: str
    theorem: str
    attempt_id: int  # For pass@k tracking


def load_benchmark_yaml(file_path: str) -> List[Tuple[str, str]]:
    """Load theorems from a YAML benchmark file"""
    with open(file_path, 'r') as f:
        data = yaml.safe_load(f)
    
    theorems = []
    for item in data:
        file_name = item['file']
        for theorem in item['theorems']:
            theorems.append((file_name, theorem))
    
    return theorems


def run_single_theorem_attempt(
    task: TheoremTask,
    tool_configs: Dict[str, Any],
    verbose: bool = False
) -> Dict[str, Any]:
    """Run a single attempt to prove a theorem"""
    thread_name = threading.current_thread().name
    
    if verbose:
        print(f"Thread {thread_name}: Starting {task.theorem} in {task.file} (attempt {task.attempt_id})")
    
    try:
        # Setup Pytanque
        pet = Pytanque(tool_configs['host'], tool_configs['port'])
        pet.connect()
        pet.set_workspace(False, str(tool_configs['workspace']))
        
        # Setup search tool
        search_tool = SearchTool(
            index_path=tool_configs['index_cache_path'],
            model=tool_configs['model_embedding'],
            api_url=tool_configs['embedding_api'],
            docstrings_path=tool_configs['docstrings_path'],
        )
        
        # Setup script tool
        script_tool = ScriptTool(
            pet=pet,
            workspace=tool_configs['workspace'],
            file=task.file,
            theorem=task.theorem,
        )
        
        # Setup have tool
        have_tool = HaveTool(
            pet=pet,
            workspace=tool_configs['workspace'],
            file=task.file,
            theorem=task.theorem,
        )
        
        # Create unique session name for this attempt
        session_name = make_session_name(f"{task.theorem}_{task.attempt_id}")
        
        # Setup LLM
        llm = API_LLM(
            api_url=tool_configs['llm_url'],
            model=tool_configs['model'],
            temperature=tool_configs['temperature'],
            verbose=verbose,
            log_dir=tool_configs['log_dir'],
            session_name=session_name,
        )
        
        # Create agent and run proof with num_attempt=1
        agent = MathProofAgent(llm, search_tool, script_tool, have_tool)
        status = agent.run_proof(num_attempt=1, verbose=verbose)
        
        result = {
            'file': task.file,
            'theorem': task.theorem,
            'attempt_id': task.attempt_id,
            'success': status.success,
            'proof': status.proof,
            'thread': thread_name
        }
        
        if verbose:
            print(f"Thread {thread_name}: {task.theorem} attempt {task.attempt_id} - {'SUCCESS' if status.success else 'FAILED'}")
        
        return result
        
    except Exception as e:
        if verbose:
            print(f"Thread {thread_name}: {task.theorem} attempt {task.attempt_id} - ERROR: {e}")
        
        return {
            'file': task.file,
            'theorem': task.theorem,
            'attempt_id': task.attempt_id,
            'success': False,
            'error': str(e),
            'thread': thread_name
        }


def run_pass_at_k(
    theorems: List[Tuple[str, str]],
    k: int,
    tool_configs: Dict[str, Any],
    max_workers: int = 4,
    verbose: bool = False
) -> Dict[str, List[Dict[str, Any]]]:
    """Run pass@k evaluation for all theorems"""
    
    # Create all tasks (k attempts per theorem)
    tasks = []
    for file_name, theorem in theorems:
        for attempt_id in range(k):
            tasks.append(TheoremTask(file_name, theorem, attempt_id))
    
    print(f"Running pass@{k} evaluation:")
    print(f"  - {len(theorems)} theorems")
    print(f"  - {k} attempts per theorem")
    print(f"  - {len(tasks)} total tasks")
    print(f"  - {max_workers} parallel workers")
    
    results = {}
    completed = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_task = {
            executor.submit(run_single_theorem_attempt, task, tool_configs, verbose): task
            for task in tasks
        }
        
        # Collect results
        for future in as_completed(future_to_task):
            task = future_to_task[future]
            result = future.result()
            
            # Group results by theorem
            theorem_key = f"{result['file']}::{result['theorem']}"
            if theorem_key not in results:
                results[theorem_key] = []
            results[theorem_key].append(result)
            
            completed += 1
            successful_attempts = sum(1 for r in results[theorem_key] if r['success'])
            
            if verbose or completed % 10 == 0:
                print(f"Progress: {completed}/{len(tasks)} completed. "
                      f"{theorem_key} - {successful_attempts}/{len(results[theorem_key])} successful")
    
    return results


def main():
    """Main entry point for batch inference CLI"""
    parser = argparse.ArgumentParser(description="Batch Coq Proof Assistant CLI with pass@k evaluation")
    
    # Input file
    parser.add_argument(
        "--benchmark", 
        type=str, 
        required=True,
        help="Path to the benchmark YAML file"
    )
    
    # Pass@k parameter
    parser.add_argument(
        "--k", 
        type=int, 
        default=1,
        help="Number of attempts per theorem for pass@k evaluation"
    )
    
    # Parallel execution
    parser.add_argument(
        "--max-workers", 
        type=int, 
        default=4,
        help="Maximum number of parallel workers"
    )
    
    # Tool configuration (same as inference-cli.py)
    parser.add_argument(
        "--workspace",
        type=str,
        default="examples",
        help="Path to the workspace directory",
    )
    parser.add_argument(
        "--host", 
        type=str, 
        default="127.0.0.1", 
        help="Pytanque server host"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=8765, 
        help="Pytanque server port"
    )
    parser.add_argument(
        "--llm-url", 
        type=str, 
        default="http://localhost:30000", 
        help="LLM API URL"
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
    parser.add_argument(
        "--verbose", 
        action="store_true", 
        help="Enable verbose output"
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default="batch_logs",
        help="Directory to store logs",
    )
    
    # Output
    parser.add_argument(
        "--output",
        type=str,
        default="batch_results.json",
        help="Output file for results"
    )
    
    args = parser.parse_args()
    
    # Load theorems from benchmark file
    theorems = load_benchmark_yaml(args.benchmark)
    print(f"Loaded {len(theorems)} theorems from {args.benchmark}")
    
    # Create tool configurations
    tool_configs = {
        'workspace': args.workspace,
        'host': args.host,
        'port': args.port,
        'llm_url': args.llm_url,
        'model': args.model,
        'temperature': args.temperature,
        'docstrings_path': args.docstrings_path,
        'index_cache_path': args.index_cache_path,
        'model_embedding': args.model_embedding,
        'embedding_api': args.embedding_api,
        'log_dir': args.log_dir,
    }
    
    # Run pass@k evaluation
    results = run_pass_at_k(
        theorems=theorems,
        k=args.k,
        tool_configs=tool_configs,
        max_workers=args.max_workers,
        verbose=args.verbose
    )
    
    # Calculate pass@k statistics
    total_theorems = len(results)
    successful_theorems = sum(1 for attempts in results.values() if any(r['success'] for r in attempts))
    
    print(f"\n=== Pass@{args.k} Results ===")
    print(f"Successful theorems: {successful_theorems}/{total_theorems} ({successful_theorems/total_theorems*100:.1f}%)")
    
    # Show per-theorem results
    if args.verbose:
        print("\nPer-theorem breakdown:")
        for theorem_key, attempts in results.items():
            successful_attempts = sum(1 for r in attempts if r['success'])
            print(f"  {theorem_key}: {successful_attempts}/{len(attempts)}")
    
    # Save results
    os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else ".", exist_ok=True)
    
    output_data = {
        'config': {
            'k': args.k,
            'total_theorems': total_theorems,
            'successful_theorems': successful_theorems,
            'pass_at_k_rate': successful_theorems / total_theorems if total_theorems > 0 else 0,
        },
        'results': results
    }
    
    with open(args.output, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()