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
from src.training_nemo.eval import start_pet_server, stop_pet_server, timeout, TimeoutError

"""
Step 2: Extract all have, rewrite them if necessary.
"""

def chunk_dataset(dataset: str, export_path: str):
    """Chunk dataset to run tasks in parallel."""

    datafile = Path(dataset)
    if not datafile.exists():
        raise Exception(f"Error: {datafile} doesn't exist.")

    with open(datafile, "r") as f:
        theorems = json.load(f)

    to_do = defaultdict(list)

    for qualid_name, theorem in theorems.items():
        theorem["fqn"] = qualid_name
        path = theorem["filepath"]
        export_filepath = Path(export_path, "aux", qualid_name + '.json')
        if not export_filepath.exists():
            to_do[path].append((qualid_name, theorem, export_filepath))

    return to_do

def make(to_do, export_path: str, petanque_port: int, source_path: str, tqdm_position: int):
    """Enclose all the have with a proof of a dataset."""

    pet_server = start_pet_server(petanque_port)
    pet = Pytanque("127.0.0.1", petanque_port)
    pet.connect()

    error_theorems = []
    count = 0
    for qualid_name, theorem, export_filepath in tqdm(to_do, desc=source_path, position=tqdm_position):
        path = Path(theorem["filepath_prefix"], theorem["filepath"])
        position = theorem["position"]
        proof = theorem["proof"]
        chain_list = proof_to_chain_list(proof)

        try:
            init_state = lambda : pet.get_state_at_pos(str(path), position["line"], position["character"], 0)
            modified, chain_list = enclose_haves(pet, init_state, chain_list)
            reproof = chain_list_to_str(chain_list)

            if modified:
                state = init_state()
                timeout(timeout)(pet.run)(state, reproof)
            else:
                assert (proof == reproof)

            theorem["proof"] = reproof
            count += 1
            with open(export_filepath, "w") as f:
                json.dump(theorem, f, indent=4)

            # if count % 1000 == 0:
            #     # reset pet-server to avoid cache overflow
            #     stop_pet_server(pet_server)
            #     pet_server = start_pet_server(petanque_port)
            #     pet = Pytanque("127.0.0.1", petanque_port)
            #     pet.connect()

        except PetanqueError as err:
            error_theorems.append(qualid_name + " -> " + err.message)
        except Exception as err:
            error_theorems.append(qualid_name + " -> " + str(err.args[0]))
        except TimeoutError as err:
            error_theorems.append(qualid_name + " -> " + "timeout")
            stop_pet_server(pet_server)
            pet_server = start_pet_server(petanque_port)
            pet = Pytanque("127.0.0.1", petanque_port)
            pet.connect()

    if len(error_theorems) > 0:
        error_file = Path(export_path, "aux", f"error_{petanque_port}.txt")
        with open(error_file, "a+") as file:
            file.write("\n".join(error_theorems))
    stop_pet_server(pet_server)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enclose all have with a proof in a dataset of theorems.")
    parser.add_argument("--input", type=str, default="export/output/steps/step_1/result.json", help="Path to the output of the previous step")
    parser.add_argument("--output", type=str, default="export/output/steps/step_2/", help="Path to output of the current step")
    parser.add_argument("--pet-timeout", type=int, default=40, help="Timeout value when running tactic")
    parser.add_argument("--max-workers", type=int, default=8, help="Number of pet server running concurrently")
    args = parser.parse_args()
    to_do = chunk_dataset(args.input, args.output)

    os.makedirs(Path(args.output, "aux"), exist_ok=True)

    with concurrent.futures.ProcessPoolExecutor(max_workers=args.max_workers) as executor:
        futures = []
        for k, source in enumerate(to_do):
            futures.append(executor.submit(make, to_do[source], args.output, 8765 + k, source, k+1))

        for _ in tqdm(concurrent.futures.as_completed(futures), desc="Overall progress", position=0, total=len(futures)):
            pass

    result = []
    errors = []
    for filepath in Path(args.output, "aux").iterdir():
        with open(filepath, 'r') as file:
            if filepath.stem.find("error") == 0:
                content = file.read()
                errors.append(content)
            else:
                content = json.load(file)
                result.append(content)

    with open(Path(args.output, f"{Path(args.input).stem}.json"), 'w') as file:
        json.dump(file, result, indent=4)

    with open(Path(args.output, f"{Path(args.input).stem}_errors.json"), 'w') as file:
        json.dump(file, errors, indent=4)
