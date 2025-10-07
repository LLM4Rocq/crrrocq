import os
import re
import json
import argparse
import concurrent.futures
from tqdm import tqdm
from pathlib import Path
from typing import Tuple
from collections import defaultdict
from pytanque import Pytanque, State, PetanqueError

from src.training.eval import start_pet_server, stop_pet_server
from src.dataset.steps.utils import is_proof_keyword, load_dictionary, update_position
from src.parser.goals import clean_goal
from src.parser.notations import notations_in_goal
from src.parser.dependencies import dependencies_in_goal

"""
Step π : extract the goal and context for each tactic.
"""

def context(pet: Pytanque, state: State, global_variables: list, filepath: str, scopes: list, dictionary: dict) -> Tuple[list, list]:
    """Return the context of a tactic."""

    # Compute the dependencies in the goal
    goals = pet.goals(state)
    goal = goals[0]
    clean_goal(goal)
    dependencies = dependencies_in_goal(pet, state, goal, [], filepath, dictionary["objects"])

    # Compute the notations in the goal
    raw_goals = pet.goals(pet.run(state, "Set Printing All."))
    raw_goal = raw_goals[0]
    clean_goal(raw_goal)
    notations = notations_in_goal(pet, state, goal, raw_goal, global_variables, filepath, scopes, dictionary["notations"])

    return goals, dependencies, notations

def tactics(pet: Pytanque, theorem: dict, dictionary: dict) -> Tuple[dict, list]:
    """Analyse a theorem tactic by tactic."""

    path = Path(theorem["filepath_prefix"], theorem["filepath"])
    tactics = []
    errors = []

    # Compute the global variables names
    global_variables = []
    for gvar in theorem["global_variables"]:
        global_variables += gvar["names"]

    for step in theorem["evaluation"]:

        if not is_proof_keyword(step["tactic"]):

            try:
                state = pet.get_state_at_pos(str(path), step["position"]["line"], step["position"]["character"], 0)
                goals, dependencies, notations = context(pet, state, global_variables, theorem["filepath"], theorem["scopes"], dictionary)
                tactics.append({
                    "filepath": theorem["filepath"],
                    "position": step["position"],
                    "goals": list(map(lambda g: g.pp, goals)),
                    "dependencies": dependencies,
                    "notations": notations,
                    "tactic": step["tactic"].strip(),
                    "target_goals": step["goals"],
                })

            except PetanqueError as err:
               errors.append((step["tactic"].strip(), "Parse error:\n" + err.message))

    return tactics, errors

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
        export_filepath = Path(export_path, qualid_name + ".json")
        error_filepath = Path(error_path, qualid_name + ".txt")
        if not export_filepath.exists() and not error_filepath.exists():
            to_do[path].append((qualid_name, theorem, export_filepath, error_filepath))
    return to_do

def make(to_do: list, dictionary: dict, petanque_port: int):
    """Compute the evaluation of all theorems in the dataset provided the dictionary."""

    pet_server = start_pet_server(petanque_port)
    pet = Pytanque("127.0.0.1", petanque_port)
    pet.connect()

    for qualid_name, theorem, export_filepath, error_filepath in tqdm(to_do):
        try:
            tacs, errors = tactics(pet, theorem, dictionary)

            result = {
                "tactics": tacs,
                "is_complete": len(errors) == 0,
            }
            with open(export_filepath, 'w') as file:
                json.dump({qualid_name: result}, file, indent=4)

            if len(errors) > 0:
                content = "Petanque:\n\n" + "\n\n".join(map(lambda p: "Tactic: " + p[0] + "\nError:\n" + p[1], errors))
                with open(error_filepath, 'w') as file:
                    file.write(content)

        except Exception as err:
            content = "Exception:\n\n" + str(err.args[0])
            with open(error_filepath, 'w') as file:
                file.write(content)

    stop_pet_server(pet_server)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract the goal and the context for each tactic of the dataset.")
    parser.add_argument("--input", type=str, default="export/output/steps/step_3/mathcomp.json", help="Path of the output of the previous step")
    parser.add_argument("--output", type=str, default="export/output/steps/step_pi/", help="Path of the output of this step")
    parser.add_argument("--dictionary", type=str, default="export/docstrings/LLM4Docq.json", help="Path of the dictionary to be used.")
    parser.add_argument("--max-workers", type=int, default=8, help="Number of pet server running concurrently")
    args = parser.parse_args()

    dataset = Path(args.input).stem
    aux_path = Path(args.output, "aux", dataset)
    os.makedirs(aux_path, exist_ok=True)
    error_path = Path(args.output, "errors", dataset)
    os.makedirs(error_path, exist_ok=True)

    to_do = chunk_dataset(args.input, aux_path, error_path)

    dictionary = load_dictionary(args.dictionary)

    with concurrent.futures.ProcessPoolExecutor(max_workers=args.max_workers) as executor:
        futures = []
        for k, source in enumerate(to_do):
            futures.append(executor.submit(make, to_do[source], dictionary, 8765 + k))
        for _ in tqdm(concurrent.futures.as_completed(futures), desc="Overall progress", position=0, total=len(futures)):
            pass

    result = {}
    for filepath in aux_path.iterdir():
        with open(filepath, 'r') as file:
            content = json.load(file)
        result = result | content

    with open(Path(args.output, f"{dataset}.json"), 'w') as file:
        json.dump(result, file, indent=4)

