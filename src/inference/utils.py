import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class ProofStep:
    """Represents a single step in a proof."""

    chain: str
    dependencies: List[Dict[str, Any]]
    goals: List[str]
    goal_diff: str


@dataclass
class ProofInfo:
    """Contains complete information about a proof."""

    statement: str
    statement_dependencies: List[Dict[str, Any]]
    global_variables: List[str]
    initial_goal: str
    evaluation: List[ProofStep]
    full_name: str


def extract_proof(
    json_data: Dict[str, Any], statement_name: str
) -> Optional[ProofInfo]:
    """
    Extract proof information for a given statement from the JSON data.

    Args:
        json_data: The parsed JSON data containing proofs
        statement_name: The name of the statement to extract (can be partial)

    Returns:
        ProofInfo object if found, None otherwise
    """
    # Find the statement (exact match first, then partial match)
    proof_key = None

    # Try exact match first
    if statement_name in json_data:
        proof_key = statement_name
    else:
        # Try partial match - find keys containing the statement name
        matching_keys = [key for key in json_data.keys() if statement_name in key]

        if len(matching_keys) == 1:
            proof_key = matching_keys[0]
        elif len(matching_keys) > 1:
            # Multiple matches - return the first one or handle as needed
            print(f"Multiple matches found for '{statement_name}': {matching_keys}")
            print(f"Using: {matching_keys[0]}")
            proof_key = matching_keys[0]
        else:
            return None

    # Extract the proof data
    proof_data = json_data[proof_key]

    # Convert evaluation steps to ProofStep objects
    evaluation_steps = []
    for step in proof_data.get("evaluation", []):
        proof_step = ProofStep(
            chain=step.get("chain", ""),
            dependencies=step.get("dependencies", []),
            goals=step.get("goals", []),
            goal_diff=step.get("goal_diff", ""),
        )
        evaluation_steps.append(proof_step)

    # Create and return ProofInfo object
    return ProofInfo(
        statement=proof_data.get("statement", ""),
        statement_dependencies=proof_data.get("statement_dependencies", []),
        global_variables=proof_data.get("global_variables", []),
        initial_goal=proof_data.get("initial_goal", ""),
        evaluation=evaluation_steps,
        full_name=proof_key,
    )


def load_and_extract_proof(file_path: str, statement_name: str) -> Optional[ProofInfo]:
    """
    Load JSON file and extract proof for a given statement.

    Args:
        file_path: Path to the JSON file
        statement_name: Name of the statement to extract

    Returns:
        ProofInfo object if found, None otherwise
    """
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            json_data = json.load(file)
        return extract_proof(json_data, statement_name)
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        return None


def print_proof_summary(proof: ProofInfo):
    """
    Print a summary of the extracted proof.

    Args:
        proof: ProofInfo object to summarize
    """
    print(f"=== PROOF: {proof.full_name} ===")
    print(f"\nStatement: {proof.statement}")
    print(f"\nGlobal Variables: {', '.join(proof.global_variables)}")
    print(f"\nStatement Dependencies: {len(proof.statement_dependencies)}")
    for dep in proof.statement_dependencies:
        print(f"  - {dep.get('name', 'Unknown')}: {dep.get('type', 'No type')}")

    print(f"\nInitial Goal:\n{proof.initial_goal}")

    print(f"\nProof Steps ({len(proof.evaluation)}):")
    for i, step in enumerate(proof.evaluation):
        print(f"  {i+1}. {step.chain}")
        if step.dependencies:
            print(
                f"     Dependencies: {[dep.get('name', 'Unknown') for dep in step.dependencies]}"
            )
        if step.goals:
            print(f"     Goals remaining: {len(step.goals)}")


def get_proof_tactics(proof: ProofInfo) -> List[str]:
    """
    Extract just the tactics/commands used in the proof.

    Args:
        proof: ProofInfo object

    Returns:
        List of tactic strings
    """
    return [step.chain.strip() for step in proof.evaluation if step.chain.strip()]


# Example usage functions
def find_all_statements(json_data: Dict[str, Any]) -> List[str]:
    """
    Get all statement names from the JSON data.

    Args:
        json_data: The parsed JSON data

    Returns:
        List of all statement names
    """
    return list(json_data.keys())


def search_statements_by_keyword(json_data: Dict[str, Any], keyword: str) -> List[str]:
    """
    Find all statements containing a keyword.

    Args:
        json_data: The parsed JSON data
        keyword: Keyword to search for

    Returns:
        List of matching statement names
    """
    return [key for key in json_data.keys() if keyword.lower() in key.lower()]


# Example usage:
if __name__ == "__main__":
    # Load from file - replace with your actual file path
    file_path = "/Users/lelarge/Recherche/LLM4code/jz_files/crrrocq_files/dataset/evaluation.json"

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            json_data = json.load(file)

        print(f"Loaded JSON data with {len(json_data)} proofs")

        # Show available statements
        print("\nAvailable statements:")
        statements = find_all_statements(json_data)
        for i, stmt in enumerate(statements, 1):
            # Extract just the lemma name from the full path
            lemma_name = stmt.split(".")[-1]
            print(f"  {i}. {lemma_name} (full: {stmt})")

        # Example: Extract a specific proof
        if statements:
            # Use the first statement as an example
            statement_name = statements[0].split(".")[-1]  # Get just the lemma name
            print(f"\n=== Extracting proof for: {statement_name} ===")

            proof = extract_proof(json_data, statement_name)

            if proof:
                print_proof_summary(proof)
                print("\nTactics used:")
                tactics = get_proof_tactics(proof)
                for tactic in tactics:
                    if tactic:  # Only show non-empty tactics
                        print(f"  - {tactic}")
            else:
                print("Proof not found")

        # Example: Search for proofs containing specific keywords
        print("\n=== Searching for proofs containing 'orthogonal' ===")
        orthogonal_proofs = search_statements_by_keyword(json_data, "orthogonal")
        for proof_name in orthogonal_proofs:
            print(f"  - {proof_name}")

    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found. Please check the file path.")
        print(
            "Make sure to update the 'file_path' variable with the correct path to your JSON file."
        )
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON file: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
