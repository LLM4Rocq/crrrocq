import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime


def make_session_name(theorem_name: str) -> str:
    """
    Generate a session name based on the theorem name.

    Args:
        theorem_name: The name of the theorem to base the session on

    Returns:
        A formatted session name string
    """
    # Use current timestamp to ensure uniqueness
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{theorem_name}_{timestamp}"


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


def parse_statement_info(statement_name: str) -> Dict[str, str]:
    """
    Parse a statement name into its components.

    Expected format: bla.bla.step_0.folder_name.file_name.lemma_name
    Or: bla.bla.step_0.folder_name.file_name.module_name.other_module.lemma_name

    Args:
        statement_name: Full statement name

    Returns:
        Dictionary with folder_name, file_name, module_name (if exists), and lemma_name
    """
    parts = statement_name.split(".")

    # Find step_0 index to locate the start of our relevant parts
    step_0_idx = None
    for i, part in enumerate(parts):
        if part.startswith("step_"):
            step_0_idx = i
            break

    if step_0_idx is None or step_0_idx + 3 >= len(parts):
        # Fallback if structure is unexpected
        return {
            "folder_name": "",
            "file_name": "",
            "module_name": "",
            "lemma_name": parts[-1] if parts else "",
        }

    # Extract components
    folder_name = parts[step_0_idx + 1]
    file_name = parts[step_0_idx + 2]
    lemma_name = parts[-1]

    # Check if there are module names between file_name and lemma_name
    module_parts = parts[
        step_0_idx + 3 : -1
    ]  # Everything between file_name and lemma_name
    module_name = ".".join(module_parts) if module_parts else ""

    return {
        "folder_name": folder_name,
        "file_name": f"{file_name}.v",
        "module_name": module_name,
        "lemma_name": lemma_name,
    }


def get_parsed_statements(json_data: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Get all statements parsed into their components.

    Args:
        json_data: The parsed JSON data

    Returns:
        List of dictionaries with parsed statement information
    """
    statements = find_all_statements(json_data)
    parsed_statements = []

    for statement in statements:
        parsed_info = parse_statement_info(statement)
        parsed_info["full_name"] = statement  # Keep the original full name
        parsed_statements.append(parsed_info)

    return parsed_statements


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


def get_evaluation_theorems(evaluation_json_path: str) -> List[Dict[str, str]]:
    """
    Extract all theorems from evaluation.json file with their folder and file information.

    Args:
        evaluation_json_path: Path to the evaluation.json file

    Returns:
        List of dictionaries containing theorem information:
        - full_name: Full statement name from JSON
        - lemma_name: Just the theorem/lemma name
        - folder_name: Folder containing the theorem
        - file_name: File containing the theorem
        - module_name: Module name if present
        - workspace_path: Constructed workspace path
    """
    try:
        with open(evaluation_json_path, "r", encoding="utf-8") as file:
            json_data = json.load(file)
    except FileNotFoundError:
        print(f"Error: File '{evaluation_json_path}' not found.")
        return []
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON file: {e}")
        return []

    theorems = []

    for statement_name in json_data.keys():
        parsed_info = parse_statement_info(statement_name)

        # Construct workspace path based on folder structure
        workspace_path = f"/lustre/fsn1/projects/rech/tdm/commun/math-comp/{parsed_info['folder_name']}"

        theorem_info = {
            "full_name": statement_name,
            "lemma_name": parsed_info["lemma_name"],
            "folder_name": parsed_info["folder_name"],
            "file_name": parsed_info["file_name"],
            "module_name": parsed_info["module_name"],
            "workspace_path": workspace_path,
        }

        theorems.append(theorem_info)

    return theorems


# Example usage:
if __name__ == "__main__":
    # Load from file - replace with your actual file path
    file_path = "/Users/lelarge/Recherche/LLM4code/jz_files/crrrocq_files/dataset/evaluation.json"
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            json_data = json.load(file)

        print(f"Loaded JSON data with {len(json_data)} proofs")

        # Show available statements with parsed information
        print("\nAvailable statements:")
        parsed_statements = get_parsed_statements(json_data)

        for i, stmt_info in enumerate(parsed_statements, 1):
            module_part = (
                f" (module: {stmt_info['module_name']})"
                if stmt_info["module_name"]
                else ""
            )
            print(
                f"  {i}. {stmt_info['lemma_name']} - {stmt_info['folder_name']}/{stmt_info['file_name']}{module_part}"
            )

        # Example: Extract a specific proof
        if parsed_statements:
            # Use the first statement as an example
            first_stmt = parsed_statements[0]
            print(f"\n=== Extracting proof for: {first_stmt['lemma_name']} ===")
            print(f"From: {first_stmt['folder_name']}/{first_stmt['file_name']}")
            if first_stmt["module_name"]:
                print(f"Module: {first_stmt['module_name']}")

            proof = extract_proof(json_data, first_stmt["lemma_name"])

            if proof:
                print_proof_summary(proof)
                print("\nTactics used:")
                tactics = get_proof_tactics(proof)
                for tactic in tactics:
                    if tactic:  # Only show non-empty tactics
                        print(f"  - {tactic}")
            else:
                print("Proof not found")

        # Example: Show statements grouped by folder
        print("\n=== Statements grouped by folder ===")
        from collections import defaultdict

        by_folder = defaultdict(list)
        for stmt in parsed_statements:
            by_folder[stmt["folder_name"]].append(stmt)

        for folder, stmts in by_folder.items():
            print(f"\n{folder}:")
            for stmt in stmts:
                module_part = (
                    f" (module: {stmt['module_name']})" if stmt["module_name"] else ""
                )
                print(f"  - {stmt['file_name']}: {stmt['lemma_name']}{module_part}")

        # Example: Search for proofs containing specific keywords
        print("\n=== Searching for proofs containing 'orthogonal' ===")
        orthogonal_proofs = search_statements_by_keyword(json_data, "orthogonal")
        for proof_name in orthogonal_proofs:
            parsed_info = parse_statement_info(proof_name)
            module_part = (
                f" (module: {parsed_info['module_name']})"
                if parsed_info["module_name"]
                else ""
            )
            print(
                f"  - {parsed_info['lemma_name']} from {parsed_info['folder_name']}/{parsed_info['file_name']}{module_part}"
            )

    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found. Please check the file path.")
        print(
            "Make sure to update the 'file_path' variable with the correct path to your JSON file."
        )
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON file: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
