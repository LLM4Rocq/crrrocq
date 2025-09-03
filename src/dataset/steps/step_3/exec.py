import re
import os
import json
import argparse
import concurrent.futures
from typing import Any, Tuple, Optional
from pathlib import Path
from collections import defaultdict

from pytanque import Pytanque, State, Goal, PetanqueError
from tqdm import tqdm

from src.training.eval import start_pet_server, stop_pet_server
from src.dataset.steps.utils import load_dictionary, append_get_index
from src.parser.haves import HaveTactic, parse_have_tags, parse_have_tactics, enclose_haves_in_proof
from src.parser.chains import proof_to_raw_chain_list
from src.parser.goals import goal_lists_diff, goal_to_lemma, pp_goal, get_hypotheses, remove_global_variables
from src.parser.notations import find_notations, format_notations, notations_in_goal
from src.parser.dependencies import find_dependencies, find_dependencies_in_hypothesis, format_dependencies, dependencies_in_goal
from src.parser.theorems import end_position, add_positions

"""
Step 3: Evaluate all theorems (goals, dependencies, etc.).
"""

# ====================
# Utils
# ====================

def update_position(line: int, char: int, text: str) -> Tuple[int, int]:
    """Return the new line and char positions after some text is added to it."""
    l, c = end_position(text)
    return add_positions(line, char, l, c)

# ====================
# Global variables
# ====================

def find_global_variables(pet: Pytanque, state: State) -> list:
    """Retrieve the global variable present at state `state`."""
    state = pet.run(state, "Goal true = true.")
    goal = pet.goals(state)[0]
    return goal.hyps

# ====================
# Haves
# ====================

def format_have_tactic(pet: Pytanque, state: State, qualid_name: str, global_variables: list[str]) -> State:
    """Format a have tactic."""
    raw_goals = pet.goals(pet.run(state, "Set Printing All."))
    raw_goal = raw_goals[0]

    name = qualid_name.rsplit('.', maxsplit=1)[-1]

    _, raw_lemma = goal_to_lemma(raw_goal, name, global_variables)

    return pet.run(state, raw_lemma + "\nUnset Printing All.")

# ====================
# Evaluation
# ====================

def evaluate_theorem(pet: Pytanque, state: State, qualid_name: str, theorem: dict[str, Any], dictionary: dict[str, Any]) -> list[Tuple[str, dict[str, Any]]]:
    """Evaluate a theorem's proof."""

    # Preprocess the proof
    parsed_proof = parse_have_tactics(theorem["proof"])

    skeleton_proof = ""
    have_idx = 0
    for segment in parsed_proof:
        if isinstance(segment, str):
            skeleton_proof += segment
        elif isinstance(segment, HaveTactic):
            skeleton_proof += segment.prefix + str(have_idx) + segment.suffix
            have_idx += 1

    # Preprocess have tactics
    have_tactics = [have_tactic for have_tactic in parsed_proof if isinstance(have_tactic, HaveTactic)]
    assert (len(have_tactics) == have_idx)

    raw_chain_list = proof_to_raw_chain_list(skeleton_proof)

    # Compute the type dictionary
    type_dictionary = {}
    type_state = pet.run(state, "Search _.")
    for s, msg in type_state.feedback:
        if s == 3:
            match = re.search(r"(?P<name>[a-zA-Z0-9_'][a-zA-Z0-9_']*[a-zA-Z0-9_']):\s(?P<type>[\s\S]*)", msg)
            if match:
                name = match.group("name").strip()
                type_ = match.group("type").strip()
                type_dictionary[name] = type_

    # Compute the global variables
    global_variables = find_global_variables(pet, state)

    global_variables_names = []
    formatted_global_variables = []
    all_notations = []
    all_dependencies = []

    # Compute the notations and dependencies in global variables
    for hyp in global_variables:
        global_variables_names += hyp.names

        # Notations in the definition
        notations = find_notations(pet, state, hyp.def_, []) if hyp.def_ else []

        # Notations in the type
        notations += find_notations(pet, state, hyp.ty, [])

        notations = format_notations(pet, state, notations, theorem["filepath"], dictionary["notations"])
        notations = [append_get_index(all_notations, notation) for notation in notations]

        # Dependencies
        dependencies = find_dependencies_in_hypothesis(pet, state, hyp, hyp.names)
        dependencies = format_dependencies(pet, state, dependencies, theorem["filepath"], type_dictionary, dictionary["objects"])
        dependencies = [append_get_index(all_dependencies, dependency) for dependency in dependencies]

        # Formatting
        if hyp.def_:
            gvar_str = "\n".join(map(lambda n: "Definition " + n + " := " + hyp.def_ + " : " + hyp.ty + ".", hyp.names))
        else:
            if len(hyp.names) > 1:
                gvar_str = "Parameters " + " ".join(hyp.names) + " : " + hyp.ty + "."
            else:
                gvar_str = "Parameter " + hyp.names[0] + " : " + hyp.ty + "."

        formatted_global_variables.append({
            "pp": gvar_str,
            "notations": notations,
            "dependencies": dependencies
        })

    # Compute the initial goal
    initial_goals = pet.goals(state)
    if len(initial_goals) != 1:
        raise Exception(f"Error: {qualid_name} starts with a number of goals different from one.")
    initial_goal = initial_goals[0]
    initial_goal_wo_gvars = remove_global_variables(initial_goal, global_variables_names)

    # Compute the statement's notations
    raw_initial_goal = pet.goals(pet.run(state, "Set Printing All."))[0]
    raw_initial_goal = remove_global_variables(raw_initial_goal, global_variables_names)
    sttt_notations = notations_in_goal(
        pet,
        state,
        initial_goal_wo_gvars,
        raw_initial_goal,
        [],
        theorem["filepath"],
        dictionary["notations"],
        theorem["exact_statement"] if "exact_statement" in theorem else None
    )
    sttt_notations = [append_get_index(all_notations, notation) for notation in sttt_notations]

    # Compute the statement's dependencies
    sttt_dependencies = dependencies_in_goal(
        pet,
        state,
        initial_goal_wo_gvars,
        [],
        theorem["filepath"],
        type_dictionary,
        dictionary["objects"],
        theorem["exact_statement"] if "exact_statement" in theorem else None
    )
    sttt_dependencies = [append_get_index(all_dependencies, dependency) for dependency in sttt_dependencies]

    # Compute the evaluation
    evaluation = []
    have_theorems = []
    previous_goals = initial_goals
    line, char = theorem["position"]["line"], theorem["position"]["character"]
    for raw_chain in raw_chain_list:
        # If there is some have tactic in the raw chain, expend it
        match = parse_have_tags(raw_chain)
        hypotheses = get_hypotheses(previous_goals[0]) if len(previous_goals) > 0 else []

        if match:
            if parse_have_tags(raw_chain[match.end():]):
                raise Exception("Error: there should be only one have tactic by raw chain.")

            idx = int(match.group("body"))
            have_tactic = have_tactics[idx]
            raw_chain_start = raw_chain[:match.start()]
            raw_chain_end = raw_chain[match.end()+1:] # The + 1 account for the point that we don't want inside of a have proof
            raw_chain = raw_chain_start + have_tactic.no_proof() + raw_chain_end

            dependencies = find_dependencies(pet, state, raw_chain_start + have_tactic.format_tactic(), hypotheses)

            state = pet.run(state, raw_chain_start + have_tactic.format_tactic())

            proof = enclose_haves_in_proof(pet, state, have_tactic.proof)
            have_qualid_name = qualid_name + '_have_' + str(idx+1)
            line, char = update_position(line, char, have_tactic.first_part())

            have_theorem = {
                "filepath_prefix": theorem["filepath_prefix"],
                "filepath": theorem["filepath"],
                "position": {"line": line, "character": char},
                "proof": proof,
                "exact_statement": have_tactic.get_statement()
            }

            line, char = update_position(line, char, have_tactic.second_part())

            try:
                have_state = format_have_tactic(pet, state, have_qualid_name, global_variables_names)
                evaluated_theorems = evaluate_theorem(pet, have_state, have_qualid_name, have_theorem, dictionary)
                have_theorems += evaluated_theorems
            except PetanqueError as err:
                pass

            state = pet.run(state, have_tactic.proof + "." + raw_chain_end)

        else:
            dependencies = find_dependencies(pet, state, raw_chain, all_dependencies + hypotheses)

            state = pet.run(state, raw_chain)

            line, char = update_position(line, char, raw_chain)

        dependencies = format_dependencies(pet, state, dependencies, theorem["filepath"], type_dictionary, dictionary["objects"])
        dependencies = [append_get_index(all_dependencies, dependency) for dependency in dependencies]

        goals = pet.goals(state)
        goals_wo_gvars = list(map(lambda g: remove_global_variables(g, global_variables_names), goals))

        evaluation.append({
            "chain": raw_chain,
            "dependencies": dependencies,
            "goals_wo_gvars": list(map(lambda g: g.pp, goals_wo_gvars)),
            "goals": list(map(lambda g: g.pp, goals)),
            "goals_diff": goal_lists_diff(previous_goals, goals)
        })

        previous_goals = goals

    if "exact_statement" in theorem:
        initial_goal_wo_gvars.ty = theorem["exact_statement"]
        initial_goal.ty = theorem["exact_statement"]

    new_theorem = {
        "filepath_prefix": theorem["filepath_prefix"],
        "filepath": theorem["filepath"],
        "position": theorem["position"],
        "global_variables": formatted_global_variables,
        "statement": {
            "initial_goal_wo_gvars": pp_goal(initial_goal_wo_gvars),
            "initial_goal": pp_goal(initial_goal),
            "notations": sttt_notations,
            "dependencies": sttt_dependencies,
        },
        "evaluation": evaluation,
        "notations": all_notations,
        "dependencies": all_dependencies
    }

    return [(qualid_name, new_theorem)] + have_theorems

def chunk_dataset(dataset: str, export_path: str):
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
        if not export_filepath.exists():
            to_do[path].append((qualid_name, theorem, export_filepath))
    return to_do

def make(to_do: str, dictionary: dict[str, Any], petanque_port: int):
    """Compute the evaluation of all theorems in the dataset provided the dictionary."""

    pet_server = start_pet_server(petanque_port)
    pet = Pytanque("127.0.0.1", petanque_port)
    pet.connect()

    for qualid_name, theorem, export_filepath in tqdm(to_do):
        try:
            path = Path(theorem["filepath_prefix"], theorem["filepath"])
            state = pet.get_state_at_pos(str(path), theorem["position"]["line"], theorem["position"]["character"], 0)
            result = dict(evaluate_theorem(pet, state, qualid_name, theorem, dictionary))

            with open(export_filepath, 'w') as file:
                json.dump(result, file, indent=4)

        except PetanqueError as err:
            print("Petanque:", qualid_name, "\n->", err.message)
        except Exception as err:
            print("Exception:", qualid_name, "\n->", str(err.args[0]))

    stop_pet_server(pet_server)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate a dataset of Rocq theorems by replaying the proof chain by chain.")
    parser.add_argument("--input", type=str, default="export/output/steps/step_2/mathcomp.json", help="Path of the output of the previous step")
    parser.add_argument("--output", type=str, default="export/output/steps/step_3/", help="Path of the output of this step")
    parser.add_argument("--dictionary", type=str, default="export/docstrings/LLM4Docq.json", help="Path of the dictionary to be used.")
    parser.add_argument("--max-workers", type=int, default=8, help="Number of pet server running concurrently")
    args = parser.parse_args()

    dataset = Path(args.input).stem
    aux_path = Path(args.output, "aux", dataset)
    os.makedirs(aux_path, exist_ok=True)

    to_do = chunk_dataset(args.input, aux_path)

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
