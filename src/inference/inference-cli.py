import argparse
from pytanque import Pytanque
from .tools import SearchTool, ScriptTool, HaveTool
from .llm import VLLM
from .agent import MathProofAgent
from .utils import extract_proof, get_proof_tactics
import json

# from src.embedding.models.qwen_embedding import Qwen3Embedding4b
# from src.embedding.index.cosim_index import FaissIndex


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
        default=0.1,
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

    parser.add_argument(
        "--eval", action="store_true", help="Running on evaluation dataset"
    )

    args = parser.parse_args()

    # Setup Pytanque
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

    if eval:
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
