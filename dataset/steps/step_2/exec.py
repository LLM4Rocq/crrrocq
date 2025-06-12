import json
import argparse
from pathlib import Path
from collections import defaultdict
import os
import concurrent.futures

from pytanque import Pytanque, PetanqueError
from tqdm import tqdm

from dataset.parser.haves import proof_to_chain_list, enclose_haves, chain_list_to_str
from src.training.eval import start_pet_server, stop_pet_server, timeout, TimeoutError

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
        export_filepath = os.path.join(export_path, 'aux', qualid_name) + '.json'
        if not os.path.exists(export_filepath):
            to_do[path].append((qualid_name, theorem, export_filepath))

    return to_do

def make(to_do, export_path: str, petanque_port: int):
    """Enclose all the have with a proof of a dataset."""

    print("Enclosing all haves in the dataset.")
    pet_server = start_pet_server(petanque_port)
    print("  Connecting to the pet-server ...")
    pet = Pytanque("127.0.0.1", petanque_port)
    pet.connect()

    print("  Enclosing the haves ...")
    error_theorems = []
    count = 0
    for qualid_name, theorem, export_filepath in tqdm(to_do):
        path = theorem["filepath"]
        position = theorem["position"]
        proof = theorem["proof"]
        chain_list = proof_to_chain_list(proof)

        try:
            init_state = lambda : pet.get_state_at_pos(path, position["line"], position["character"], 0)
            modified, chain_list = enclose_haves(pet, init_state, chain_list)
            reproof = chain_list_to_str(chain_list)

            if modified:
                state = init_state()
                timeout(40)(pet.run)(state, reproof)
            else:
                assert (proof == reproof)

            theorem["proof"] = reproof
            count += 1
            with open(export_filepath, "w") as f:
                json.dump(theorem, f, indent=4)
            
            if count % 1000 == 0:
                # reset pet-server to avoid cache overflow
                stop_pet_server(pet_server)
                pet_server = start_pet_server(petanque_port)

        except PetanqueError as err:
            error_theorems.append(qualid_name + " -> " + err.message)
        except Exception as err:
            error_theorems.append(qualid_name + " -> " + str(err.args[0]))
        except TimeoutError as err:
            error_theorems.append(qualid_name + " -> " + "timeout")
            stop_pet_server(pet_server)
            pet_server = start_pet_server(petanque_port)

    error_file = os.path.join(export_path, 'aux', f'error_{petanque_port}')
    with open(error_file, "a+") as file:
        file.write("\n".join(error_theorems))
    stop_pet_server(pet_server)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enclose all have with a proof in a dataset of theorems.")
    parser.add_argument("--input", type=str, default="export/output/steps/step_1/result.json", help="Path to the output of the previous step")
    parser.add_argument("--output", type=str, default="export/output/steps/step_2/", help="Path to output of the current step")
    parser.add_argument("--max-workers", type=int, default=8, help="Number of pet server running concurrently")
    args = parser.parse_args()
    to_do = chunk_dataset(args.input, args.output)

    os.makedirs(os.path.join(args.output, 'aux'), exist_ok=True)
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.max_workers) as executor:
        futures = []
        for k, source in enumerate(to_do):
            futures.append(executor.submit(make, to_do[source], args.output, 8765 + k))

        for _ in tqdm(concurrent.futures.as_completed(futures), desc="Overall progress", position=0, total=len(futures)):
            pass
    
    result = []
    for filename in os.listdir(os.path.join(args.output, 'aux')):
        filepath = os.path.join(args.output, filename)
        with open(filepath, 'r') as file:
            content =json.load(file)
        result.append(content)
    
    with open(os.path.join(args.ouput, 'result.json'), 'r') as file:
        json.dump(file, result, indent=4)