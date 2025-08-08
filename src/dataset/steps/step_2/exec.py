import json
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Callable
import os
import concurrent.futures

from pytanque import Pytanque, PetanqueError
from tqdm import tqdm

from src.parser.haves import proof_to_chain_list, enclose_haves, chain_list_to_str
from src.training.eval import start_pet_server, stop_pet_server, timeout, TimeoutError

"""
Step 2: Extract all have, rewrite them if necessary.
"""

def chunk_dataset(dataset: str, export_path: str, error_path: str):
    """Chunk dataset to run tasks in parallel."""

    datafile = Path(dataset)
    if not datafile.exists():
        raise Exception(f"Error: {datafile} doesn't exist.")

    with open(datafile, "r") as f:
        theorems = json.load(f)

    to_do = defaultdict(list)

    for qualid_name, theorem in theorems.items():
        path = theorem["filepath"]
        export_filepath = Path(export_path, qualid_name + '.json')
        error_filepath = Path(error_path, qualid_name + '.json')
        if not export_filepath.exists() and not error_filepath.exists():
            to_do[path].append((theorem, export_filepath, error_filepath))

    return to_do

def make(to_do, petanque_port: int, pet_timeout: int):
    """Enclose all the have with a proof of a dataset."""

    pet_server = start_pet_server(petanque_port)
    pet = Pytanque("127.0.0.1", petanque_port)
    pet.connect()

    for theorem, export_filepath, error_filepath in tqdm(to_do):
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
            else:
                assert (proof == reproof)

            theorem["proof"] = reproof
            with open(export_filepath, "w") as f:
                json.dump(theorem, f, indent=4)

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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enclose all have with a proof in a dataset of theorems.")
    parser.add_argument("--input", type=str, default="export/output/steps/step_1/mathcomp.json", help="Path of the output of the previous step")
    parser.add_argument("--output", type=str, default="export/output/steps/step_2/", help="Path of the output of this step")
    parser.add_argument("--pet-timeout", type=int, default=40, help="Timeout value when running tactic")
    parser.add_argument("--max-workers", type=int, default=8, help="Number of pet server running concurrently")
    args = parser.parse_args()

    dataset = Path(args.input).stem
    aux_path = Path(args.output, "aux", dataset)
    os.makedirs(aux_path, exist_ok=True)
    error_path = Path(args.output, "errors", dataset)
    os.makedirs(error_path, exist_ok=True)

    to_do = chunk_dataset(args.input, aux_path, error_path)

    with concurrent.futures.ProcessPoolExecutor(max_workers=args.max_workers) as executor:
        futures = []
        for k, source in enumerate(to_do):
            futures.append(executor.submit(make, to_do[source], 8765 + k, args.pet_timeout))

        for _ in tqdm(concurrent.futures.as_completed(futures), desc="Overall progress", position=0, total=len(futures)):
            pass

    result = {}
    for filepath in aux_path.iterdir():
        with open(filepath, 'r') as file:
            content = json.load(file)
            result[filepath.stem] = content

    with open(Path(args.output, f"{dataset}.json"), 'w') as file:
        json.dump(result, file, indent=4)

    errors = {}
    for filepath in error_path.iterdir():
        with open(filepath, 'r') as file:
            content = json.load(file)
            errors[filepath.stem] = content

    with open(Path(args.output, f"{dataset}_errors.json"), 'w') as file:
        json.dump(errors, file, indent=4)
