import os
import sys
import json
import time
import argparse
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from pass_at_k_prover import PassAtKProver
from tools import ScriptTool
from llm import VLLM
from pytanque import Pytanque


class BenchmarkRunner:
    """
    Runs the pass@k algorithm on a benchmark of Coq theorems.

    The benchmark is made of various files where each file contains one theorem to prove.
    The name of the file is the name of the theorem.
    """

    def __init__(
        self,
        benchmark_dir: str,
        workspace_dir: str = None,
        llm_url: str = "http://localhost:8000",
        model: str = "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B",
        k: int = 3,
        max_iterations: int = 10,
        temperature: float = 0.7,
        goals_tag: str = "GOALS",
        result_tag: str = "r",
        host: str = "127.0.0.1",
        port: int = 8765,
        timeout: int = 300,  # 5 minutes per theorem
        parallel: bool = False,
        verbose: bool = False,
        context: bool = False,
        llm_log_dir: str = "llm_logs",
    ):
        """
        Initialize the benchmark runner.

        Args:
            benchmark_dir: Directory containing theorem files
            workspace_dir: Directory to use as the workspace (default: benchmark_dir)
            llm_url: URL of the LLM API
            model: Name of the model to use
            k: Number of parallel paths for pass@k
            max_iterations: Maximum iterations per theorem
            temperature: Temperature for LLM generation
            goals_tag: XML tag for goals
            result_tag: Tag for result output
            host: Pytanque server host
            port: Pytanque server port
            timeout: Maximum time in seconds per theorem
            parallel: Whether to run theorems in parallel
            verbose: Whether to print verbose output
        """
        self.benchmark_dir = os.path.abspath(benchmark_dir)
        self.workspace_dir = (
            os.path.abspath(workspace_dir) if workspace_dir else self.benchmark_dir
        )
        self.llm_url = llm_url
        self.model = model
        self.k = k
        self.max_iterations = max_iterations
        self.temperature = temperature
        self.goals_tag = goals_tag
        self.result_tag = result_tag
        self.host = host
        self.port = port
        self.timeout = timeout
        self.parallel = parallel
        self.verbose = verbose
        self.context = context

        # Connect to Pytanque
        self.pet = Pytanque(host, port)
        self.pet.connect()
        self.pet.set_workspace(False, str(self.workspace_dir))

        # Setup LLM
        self.llm = VLLM(
            api_url=llm_url,
            model=model,
            temperature=temperature,
            verbose=verbose,
        )

        # Results storage
        self.results = {}

        # Setup LLM
        self.llm = VLLM(
            api_url=llm_url,
            model=model,
            temperature=temperature,
            verbose=verbose,
            log_dir=llm_log_dir,
            log_to_console=verbose,
        )

    def discover_theorems(self) -> List[Tuple[str, str]]:
        """
        Discover theorems in the benchmark directory.

        Returns:
            List of (filename, theorem_name) tuples
        """
        theorems = []

        for filename in os.listdir(self.benchmark_dir):
            if filename.endswith(".v"):
                # The theorem name is the filename without extension
                theorem_name = os.path.splitext(filename)[0]
                theorems.append((filename, theorem_name))

        return theorems

    def prove_theorem(self, filename: str, theorem_name: str) -> Dict[str, Any]:
        """
        Try to prove a single theorem.

        Args:
            filename: Coq file name
            theorem_name: Name of the theorem to prove

        Returns:
            Dictionary with results
        """
        start_time = time.time()

        # Create ScriptTool for this theorem
        coq_tool = ScriptTool(
            pet=self.pet,
            workspace=self.workspace_dir,
            file=filename,
            theorem=theorem_name,
            context=self.context,
        )

        # Create prover
        prover = PassAtKProver(
            llm=self.llm,
            coq_tool=coq_tool,
            k=self.k,
            max_iterations=self.max_iterations,
            verbose=self.verbose,
            goals_tag=self.goals_tag,
            result_tag=self.result_tag,
        )

        try:
            # Set timeout using signal
            import signal

            def timeout_handler(signum, frame):
                raise TimeoutError(f"Timeout after {self.timeout} seconds")

            # Set timeout
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(self.timeout)

            # Run the prover
            success, proof = prover.run_pass_at_k()

            # Cancel timeout
            signal.alarm(0)

            end_time = time.time()
            duration = end_time - start_time

            # Prepare result
            result = {
                "theorem": theorem_name,
                "file": filename,
                "success": success,
                "duration": duration,
                "proof": proof if success else None,
                "proof_length": len(proof) if success else 0,
                "timestamp": datetime.now().isoformat(),
            }

            return result

        except TimeoutError as e:
            if self.verbose:
                print(f"Timeout proving {theorem_name}: {e}")

            return {
                "theorem": theorem_name,
                "file": filename,
                "success": False,
                "duration": self.timeout,
                "proof": None,
                "proof_length": 0,
                "error": "timeout",
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            if self.verbose:
                print(f"Error proving {theorem_name}: {e}")

            return {
                "theorem": theorem_name,
                "file": filename,
                "success": False,
                "duration": time.time() - start_time,
                "proof": None,
                "proof_length": 0,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def run_benchmark(self) -> Dict[str, Any]:
        """
        Run the benchmark on all theorems.

        Returns:
            Dictionary with benchmark results
        """
        # Discover theorems
        theorems = self.discover_theorems()

        if self.verbose:
            print(f"Found {len(theorems)} theorems to benchmark")

        # Run benchmarks in sequence
        for filename, theorem_name in theorems:
            if self.verbose:
                print(f"Proving theorem {theorem_name} from {filename}...")

            result = self.prove_theorem(filename, theorem_name)

            if self.verbose:
                success_str = "SUCCESS" if result["success"] else "FAILED"
                duration_str = f"{result['duration']:.2f}s"
                print(f"  {success_str} in {duration_str}")

            self.results[theorem_name] = result

        # Generate summary
        benchmark_summary = self.generate_summary()

        return benchmark_summary

    def generate_summary(self) -> Dict[str, Any]:
        """
        Generate a summary of benchmark results.

        Returns:
            Dictionary with benchmark summary
        """
        total_theorems = len(self.results)
        successful_theorems = sum(
            1 for result in self.results.values() if result["success"]
        )
        success_rate = successful_theorems / total_theorems if total_theorems > 0 else 0

        total_duration = sum(result["duration"] for result in self.results.values())
        avg_duration = total_duration / total_theorems if total_theorems > 0 else 0

        successful_proofs = [
            result for result in self.results.values() if result["success"]
        ]
        avg_proof_length = (
            sum(proof["proof_length"] for proof in successful_proofs)
            / len(successful_proofs)
            if successful_proofs
            else 0
        )

        # Find fastest and slowest theorems
        fastest_theorem = (
            min(self.results.values(), key=lambda x: x["duration"])
            if self.results
            else None
        )
        slowest_theorem = (
            max(self.results.values(), key=lambda x: x["duration"])
            if self.results
            else None
        )

        # Create summary
        summary = {
            "total_theorems": total_theorems,
            "successful_theorems": successful_theorems,
            "success_rate": success_rate,
            "total_duration": total_duration,
            "avg_duration": avg_duration,
            "avg_proof_length": avg_proof_length,
            "fastest_theorem": fastest_theorem["theorem"] if fastest_theorem else None,
            "fastest_time": fastest_theorem["duration"] if fastest_theorem else None,
            "slowest_theorem": slowest_theorem["theorem"] if slowest_theorem else None,
            "slowest_time": slowest_theorem["duration"] if slowest_theorem else None,
            "parameters": {
                "k": self.k,
                "max_iterations": self.max_iterations,
                "temperature": self.temperature,
                "model": self.model,
            },
            "timestamp": datetime.now().isoformat(),
            "results": self.results,
        }

        return summary

    def save_results(self, output_dir: str, filename: str = None) -> str:
        """
        Save benchmark results to a JSON file.

        Args:
            output_dir: Directory to save results
            filename: Optional specific filename (default: auto-generated)

        Returns:
            Path to the saved file
        """
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Generate filename if not provided
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"benchmark_k{self.k}_t{self.temperature:.1f}_{timestamp}.json"

        # Generate summary
        summary = self.generate_summary()

        # Save to file
        output_path = os.path.join(output_dir, filename)
        with open(output_path, "w") as f:
            json.dump(summary, f, indent=2)

        if self.verbose:
            print(f"Saved benchmark results to {output_path}")

        return output_path


def main():
    """Main entry point for the benchmark runner CLI."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Pass@k Benchmark Runner")

    # Benchmark configuration
    parser.add_argument(
        "--benchmark-dir",
        type=str,
        required=True,
        help="Directory containing theorem files",
    )
    parser.add_argument(
        "--workspace-dir",
        type=str,
        help="Directory to use as workspace (default: benchmark-dir)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./benchmark_results",
        help="Directory to save results (default: ./benchmark_results)",
    )

    # Prover configuration
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
        help="Maximum number of iterations per theorem",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Maximum time in seconds per theorem (default: 300)",
    )

    # LLM configuration
    parser.add_argument(
        "--llm-url",
        type=str,
        default="http://localhost:8000",
        help="URL of the LLM API",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B",
        help="LLM model name",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="Temperature for LLM generation",
    )

    # Tag configuration
    parser.add_argument(
        "--goals-tag",
        type=str,
        default="GOALS",
        help="XML tag for goals",
    )
    parser.add_argument(
        "--result-tag",
        type=str,
        default="r",
        help="Tag for result output",
    )

    # Pytanque configuration
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Pytanque server host",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Pytanque server port",
    )

    # Misc configuration
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
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

    # Create and run benchmark
    benchmark = BenchmarkRunner(
        benchmark_dir=args.benchmark_dir,
        workspace_dir=args.workspace_dir,
        llm_url=args.llm_url,
        model=args.model,
        k=args.k,
        max_iterations=args.max_iterations,
        temperature=args.temperature,
        goals_tag=args.goals_tag,
        result_tag=args.result_tag,
        host=args.host,
        port=args.port,
        timeout=args.timeout,
        verbose=args.verbose,
        context=args.context,
        llm_log_dir=args.llm_log_dir,
    )

    # Run benchmark
    start_time = time.time()
    summary = benchmark.run_benchmark()
    end_time = time.time()

    # Save results
    benchmark.save_results(args.output_dir)

    # Print summary
    total_time = end_time - start_time
    print("\nBenchmark completed!")
    print(f"Total time: {total_time:.2f}s")
    print(f"Total theorems: {summary['total_theorems']}")
    print(
        f"Successful theorems: {summary['successful_theorems']} ({summary['success_rate']*100:.1f}%)"
    )
    print(f"Average duration per theorem: {summary['avg_duration']:.2f}s")
    if summary["successful_theorems"] > 0:
        print(f"Average proof length: {summary['avg_proof_length']:.1f} tactics")


if __name__ == "__main__":
    main()
