import json
import os
import concurrent.futures
import argparse
import shutil
from pathlib import Path
from collections import defaultdict
from typing import Callable

from pytanque import Pytanque, PetanqueError
from tqdm import tqdm

from src.dataset.steps.utils import get_rocq_files
from src.parser.theorems import read_theorems_in_file, format_theorem
from src.parser.haves import proof_to_chain_list, enclose_haves, chain_list_to_str
from src.training.eval import start_pet_server, stop_pet_server, timeout, TimeoutError

"""
Step 1: Extract all have, rewrite them if necessary, and create a new dataset.
"""

# ====================
# Manipulate the dataset.
# ====================

def trim_prefix(parent_dir: Path, prefix: str) -> str:
    """Remove the part corresponding to the parent directory in a prefix."""
    parent_dir = (str(parent_dir) + '/').replace('/', '.')
    return prefix.replace(parent_dir, "")

def trim_filepath(parent_dir: Path, filepath: Path) -> str:
    """Remove the part corresponding to the parent directory in a filepath."""
    return str(filepath).replace(str(parent_dir) + '/', "")

def read_dataset(dataset: Path, export_dir: str) -> Path:
    """Read the dataset and return its new path."""

    files = get_rocq_files(dataset)

    theorems = []
    for file in tqdm(files, desc="Reading"):
        file_theorems = read_theorems_in_file(file)
        theorems += [(file, trim_prefix(dataset.parent, prefix), theorem) for prefix, theorem in file_theorems]

    theorems = [(str(dataset.parent), trim_filepath(dataset.parent, file), format_theorem(prefix, theorem, file)) for file, prefix, theorem in tqdm(theorems)]
    theorems = {qualid_name: {"filepath_prefix": pfile, "filepath": file} | theorem for pfile, file, (qualid_name, theorem) in theorems}

    print("  Total number of theorems:", len(list(theorems)))

    new_dataset = Path(export_dir, f"{dataset.stem}.json")
    with open(new_dataset, 'w') as f:
        json.dump(theorems, f, indent=4)

    return new_dataset

def copy_dataset(dataset: Path, export_dir: str) -> Path:
    """Copy the dataset to a new directory and return its new path."""
    new_dataset = Path(export_dir, dataset.stem)
    shutil.copytree(dataset, new_dataset, dirs_exist_ok=True)
    return new_dataset

def chunk_dataset(dataset: Path, export_dir: str, error_path: str):
    """Chunk dataset to run tasks in parallel."""

    if not dataset.exists():
        raise Exception(f"Error: {dataset} doesn't exist.")

    dataset = read_dataset(dataset, export_dir)

    with open(dataset, 'r') as f:
        theorems = json.load(f)

    to_do = defaultdict(list)

    for qualid_name, theorem in theorems.items():
        path = theorem["filepath"]
        error_filepath = Path(error_path, qualid_name + '.json')
        if not error_filepath.exists():
            to_do[path].append((theorem, error_filepath))

    return to_do

# ====================
# Extract have proofs
# ====================

def make(filepath: str, export_dir: str, to_do, petanque_port: int, pet_timeout: int):
    """Enclose all the have with a proof of a dataset."""

    pet_server = start_pet_server(petanque_port)
    pet = Pytanque("127.0.0.1", petanque_port)
    pet.connect()

    to_modify = []

    # Treat each theorem in a file
    for theorem, error_filepath in tqdm(to_do):
        path = Path(theorem["filepath_prefix"], theorem["filepath"])
        position = theorem["position"]
        proof = theorem["proof"]
        chain_list = proof_to_chain_list(proof)

        error = ""
        try:
            init_state = lambda : pet.get_state_at_pos(str(path), position["line"], position["character"], 0)
            modified, chain_list = enclose_haves(pet, init_state, chain_list)
            reproof = chain_list_to_str(chain_list)

            if modified:
                state = init_state()
                timeout(pet_timeout)(pet.run)(state, reproof)
                to_modify.append((proof, reproof))
            else:
                assert (proof == reproof)

        except PetanqueError as err:
            error = "-> " + err.message
        except Exception as err:
            error = "-> " + str(err.args[0])
        except TimeoutError as err:
            error = "-> timeout"
            stop_pet_server(pet_server)
            pet_server = start_pet_server(petanque_port)
            pet = Pytanque("127.0.0.1", petanque_port)
            pet.connect()

        if len(error) > 0:
            theorem["error"] = error
            with open(error_filepath, 'w') as file:
                json.dump(theorem, file, indent=4)

    stop_pet_server(pet_server)

    # Change all modified proof of theorems
    new_filepath = Path(export_dir, filepath)
    with open(new_filepath, 'r') as file:
        content = file.read()

    for proof, reproof in to_modify:
        content = content.replace(proof, reproof)

    with open(new_filepath, 'w') as file:
        file.write(content)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enclose all have with a proof in a dataset of theorems.")
    parser.add_argument("--input", type=str, default="export/output/steps/step_0/mathcomp", help="Path of the output of the previous step")
    parser.add_argument("--output", type=str, default="export/output/steps/step_1/", help="Path of the output of this step")
    parser.add_argument("--pet-timeout", type=int, default=40, help="Timeout value when running tactic")
    parser.add_argument("--max-workers", type=int, default=8, help="Number of pet server running concurrently")
    args = parser.parse_args()

    dataset = Path(args.input).stem
    error_path = Path(args.output, "errors", dataset)
    os.makedirs(error_path, exist_ok=True)

    # Copy the dataset
    new_dataset = copy_dataset(Path(args.input), args.output)

    # Chunk the dataset
    to_do = chunk_dataset(Path(args.input), args.output, error_path)

    with concurrent.futures.ProcessPoolExecutor(max_workers=args.max_workers) as executor:
        futures = []
        for k, source in enumerate(to_do):
            futures.append(executor.submit(make, source, args.output, to_do[source], 8765 + k, args.pet_timeout))

        for _ in tqdm(concurrent.futures.as_completed(futures), desc="Overall progress", position=0, total=len(futures)):
            pass

    # Gather errors
    errors = {}
    for filepath in error_path.iterdir():
        with open(filepath, 'r') as file:
            content = json.load(file)
            errors[filepath.stem] = content

    with open(Path(args.output, f"{dataset}_errors.json"), 'w') as file:
        json.dump(errors, file, indent=4)

    # Read the dataset
    dataset_json = read_dataset(new_dataset, args.output)

    # Remove errors from the dataset
    with open(dataset_json, 'r') as file:
        results = json.load(file)

    for error in errors:
        results.pop(error)

    print("  Final number of theorems:", len(results))

    with open(dataset_json, 'w') as file:
        json.dump(results, file, indent=4)
