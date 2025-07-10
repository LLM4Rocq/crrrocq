import re
import json
import argparse
from typing import Any, Tuple, Optional
from pathlib import Path
from collections import defaultdict
import os
import concurrent.futures

from pytanque import Pytanque, State, Goal, PetanqueError
from tqdm import tqdm

from src.training.eval import start_pet_server, stop_pet_server
from src.parser.ast import list_dependencies
from src.parser.haves import HaveTactic, parse_have_tags, parse_have_tactics, enclose_haves_in_proof
from src.parser.chains import proof_to_raw_chain_list, raw_chain_list_to_str
from src.parser.goals import goal_lists_diff, replace_list, goal_to_lemma, goal_to_lemma_def

"""
Step 4: Evaluate all theorems (goals, dependencies, etc.).
"""

# ====================
# Utils
# ====================

def load_dictionary(dfile: str) -> dict:
    """Load the dictionary."""

    with open(dfile, 'r') as file:
        d_base = json.load(file)

    d = {"objects": {}, "notations": d_base["notations"]}

    for keys, value in d_base["objects"]:
        for key in keys:
            d["objects"][key] = value

    return d

# ====================
# Notations
# ====================

def find_notations(pet: Pytanque, state: State, code: str) -> list[str]:
    """Find all notations appearing in `code`."""
    pre_notation_list = pet.list_notations_in_statement(state, code)

    notation_list = {"scope": {}, "noscope": {}}
    for cnot in pre_notation_list:
        qualid_name = cnot["path"] + ('.' + cnot["secpath"] if cnot["secpath"] != "<>" else "") + '.' + cnot["notation"]
        if cnot["scope"]:
            if not cnot["scope"] in notation_list["scope"]:
                notation_list["scope"][cnot["scope"]] = {}
            d = notation_list["scope"][cnot["scope"]]
        else:
            d = notation_list["noscope"]

        d[qualid_name] = {"name": cnot["notation"]}

    return notation_list

def format_notations(pet: Pytanque, state: State, notation_list: list, filepath: str, dictionary: dict[str, str]) -> list:
    """Format notations."""

    filepath = Path(filepath)
    filename = filepath.stem

    new_notations_list = {"scope": {scope: {} for scope in notation_list["scope"]}, "noscope": {}}

    # Iter over notations with scope and notations without scope
    all_notations = []
    for scope, scope_notations in notation_list["scope"].items():
        if scope in dictionary["scope"]:
            all_notations.append((new_notations_list["scope"][scope], scope_notations, dictionary["scope"][scope]))
    all_notations.append((new_notations_list["noscope"], notation_list["noscope"], dictionary["noscope"]))

    for save_notations, notations, dictionary in all_notations:
        for qname, notation in notations.items():

            # Check if the notation is declared in the same file that the state is in
            if filename == qname.split('.', maxsplit=1)[0]:
                qname = '.'.join(list(filepath.parent.parts) + [qname])

            # Locate the notation
            lstate = pet.run(state, f'Locate "{notation["name"]}".')
            message = lstate.feedback[0][1]

            # Extract all notations found by locate
            ntns = []
            for match in re.finditer(r'Notation\s(?P<notation>"[\s\S]+?")\s:=', message):
                ntn_name = match.group("notation")
                ntns.append(ntn_name)

            # Keep only the notations inside of the notations dictionary
            dntns = []
            for ntn_name in ntns:
                ntn_qname = qname.replace(notation["name"], "") + ntn_name
                if ntn_qname in dictionary and not ntn_qname in dntns:
                    dntns.append(ntn_qname)

            # There should be exactly one match
            if len(dntns) == 0:
                pass
                # print("NOTATION:", qname) # for debugging
            elif len(dntns) > 1:
                pass
                # print("NOTATIONS:", dntns) # for debugging
            else:
                qname = dntns[0]
                save_notations[qname] = notation | {"info": dictionary[qname]}

    return new_notations_list

# ====================
# Dependencies
# ====================

def find_dependencies(pet: Pytanque, state: State, code: str, bad: list[str]) -> list[str]:
    """Find all dependencies of `code` that are not in `bad`."""
    ast = pet.ast(state, code)
    dependencies = list_dependencies(ast)

    goals = pet.goals(state)
    hypotheses = []
    if len(goals) > 0:
        goal = goals[0]
        for hyp in goal.hyps:
            hypotheses += hyp.names

    return [dependency for dependency in dependencies if not dependency in bad + hypotheses]

def format_dependency(pet: Pytanque, state: State, dependency: str, filepath: str, search_dictionary: dict[str, str], info_dictionary: dict[str, Any]) -> Optional[dict[str, str]]:
    """Format a dependency."""

    state = pet.run(state, f"Locate Term {dependency}.")
    if len(state.feedback) == 0:
        raise Exception(f"Error: there should be at least one feedback when doing `Locate Term {dependency}.`.")
    message = state.feedback[0][1]

    # Check if the dependency is syntactically equal to another theorem
    match = re.search(r"(Constant|Inductive|Constructor)\s*(?P<first_qualid_name>\S*)\s*\(syntactically\s*equal\s*to\s*(?P<second_qualid_name>\S*)\s*\)", message)
    if match and match.start() == 0:
        qualid_names = [match.group("first_qualid_name"), match.group("second_qualid_name")]

    else:
        # Check for normal dependency
        match = re.search(r"(Constant|Inductive|Constructor)\s(?P<qualid_name>\S*)", message)
        if match and match.start() == 0:
            qualid_names = [match.group("qualid_name")]

        else:
            # Check for notation dependency
            match = re.search(r"Notation\s(?P<qualid_name>\S*)", message)
            if match and match.start() == 0:
                qualid_names = [match.group("qualid_name")]

            else:
                # print("NONE, DEP:", dependency)
                return None

    res = {"name": dependency}
    if dependency in search_dictionary:
        res["type"] = search_dictionary[dependency]

    filepath = Path(filepath)
    filename = filepath.stem
    for qname in qualid_names:

        # Check if the dependency is declared in the same file that the state is in
        if filename == qname.split('.', maxsplit=1)[0]:
            qname = '.'.join(list(filepath.parent.parts) + [qname])

        if qname in info_dictionary:
            res["info"] = info_dictionary[qname]
            break

    if not "info" in res:
        print("INFO, QUALID NAMES:", qualid_names)
    if not "type" in res:
        print("TYPE, QUALID NAMES:", qualid_names)

    return res

def format_dependencies(pet: Pytanque, state: State, dependencies: list[str], filepath: str, search_dictionary: dict[str, str], info_dictionary: dict[str, Any]) -> list[dict[str, str]]:
    """Format dependencies."""

    dependencies = [format_dependency(pet, state, dependency, filepath, search_dictionary, info_dictionary) for dependency in dependencies]
    return [dependency for dependency in dependencies if dependency]

# ====================
# Global variables
# ====================

def find_global_variables(pet: Pytanque, state: State) -> list[str]:
    """Retrieve the global variable present at state `state`."""
    state = pet.run(state, "Goal true = true.")
    goal = pet.goals(state)[0]
    global_variables = []
    for hyp in goal.hyps:
        global_variables += hyp.names
    return global_variables

# ====================
# Haves
# ====================

def split_have_proofs(pet: Pytanque, state: State, previous_goals: list[Goal], have_proof: str, qualid_name: str, global_variables: list[str]) -> list[Tuple[State, str, str, str, str]]:
    """Split the proofs of a have tactic."""
    base_state = state
    goals = pet.goals(base_state)
    raw_goals = pet.goals(pet.run(base_state, "Set Printing All."))
    raw_chain_list = proof_to_raw_chain_list(have_proof)

    have_proofs = []
    current_proof = ""
    goal_count = 1
    i = 0
    while i < len(raw_chain_list) and len(goals) - len(previous_goals) > 1:

        state = pet.run(state, raw_chain_list[i])
        current_proof += raw_chain_list[i]
        current_goals = pet.goals(state)

        # If we solved one goal
        if len(goals) > len(current_goals):
            goal = goals.pop(0)
            raw_goal = raw_goals.pop(0)

            current_qualid_name = qualid_name + '_' + str(goal_count)
            name = current_qualid_name.rsplit('.', maxsplit=1)[-1]
            goal_count += 1

            _, lemma = goal_to_lemma(goal, name, global_variables)
            renamed, raw_lemma = goal_to_lemma(raw_goal, name, global_variables)

            have_proofs.append((pet.run(base_state, raw_lemma), current_qualid_name, lemma, raw_lemma, replace_list(current_proof, renamed)))
            current_proof = ""

        i += 1

    goal = goals.pop(0)
    raw_goal = raw_goals.pop(0)

    current_qualid_name = qualid_name + ('_' + str(goal_count) if goal_count > 1 else "")
    name = current_qualid_name.rsplit('.', maxsplit=1)[-1]

    _, lemma = goal_to_lemma(goal, name, global_variables)
    renamed, raw_lemma = goal_to_lemma(raw_goal, name, global_variables)

    last_proof = raw_chain_list_to_str(raw_chain_list[i:])
    have_proofs.append((pet.run(base_state, raw_lemma), current_qualid_name, lemma, raw_lemma, replace_list(last_proof, renamed)))

    return have_proofs

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

    # Compute the global variables
    global_variables = find_global_variables(pet, state)

    # Compute the initial goal and hypotheses
    initial_goals = pet.goals(state)
    if len(initial_goals) != 1:
        raise Exception(f"Error: {qualid_name} starts with a number of goals different from one.")
    initial_goal = initial_goals[0]
    hypotheses = []
    for hyp in initial_goal.hyps:
        for name in hyp.names:
            hypotheses.append(name)
    # /!\ global variables are included in initial hypotheses /!\

    # Compute the valid_names
    search_state = pet.run(state, "Search _.")
    search_dictionary = {}
    for s, info in search_state.feedback:
        match = re.search(r"(?P<name>[a-zA-Z0-9_'][a-zA-Z0-9_']*[a-zA-Z0-9_']):\s(?P<type>[\s\S]*)", info)
        if s == 3 and match and match.start() == 0:
            name = match.group("name").strip()
            type_ = match.group("type").strip()
            if not name in hypotheses:
                search_dictionary[name] = type_

    # Compute the statement's dependencies
    try:
        sttt_notations = find_notations(pet, state, theorem["statement"])
    except PetanqueError as err:
        name = qualid_name.rsplit('.', maxsplit=1)[-1]
        _, lemma = goal_to_lemma_def(initial_goal, name, global_variables)
        sttt_notations = find_notations(pet, state, lemma)
    sttt_notations = format_notations(pet, state, sttt_notations, theorem["filepath"], dictionary["notations"])

    sttt_dependencies = find_dependencies(pet, state, theorem["statement"], [])
    sttt_dependencies = format_dependencies(pet, state, sttt_dependencies, theorem["filepath"], search_dictionary, dictionary["objects"])
    known_dependencies = [dependency["name"] for dependency in sttt_dependencies]

    # Compute the evaluation
    evaluation = []
    have_theorems = []
    previous_goals = initial_goals
    for raw_chain in raw_chain_list:
        # If there is some have tactic in the raw chain, expend it
        match = parse_have_tags(raw_chain)

        if match:
            if parse_have_tags(raw_chain[match.end():]):
                raise Exception("Error: there should be only one have tactic by raw chain.")

            idx = int(match.group("body"))
            have_tactic = have_tactics[idx]
            raw_chain_start = raw_chain[:match.start()]
            raw_chain_end = raw_chain[match.end()+1:] # The + 1 account for the point that we don't want inside of a have proof
            raw_chain = raw_chain_start + have_tactic.no_proof() + raw_chain_end

            dependencies = find_dependencies(pet, state, raw_chain_start + have_tactic.tactic, known_dependencies)
            dependencies = format_dependencies(pet, state, dependencies, theorem["filepath"], search_dictionary, dictionary["objects"])

            state = pet.run(state, raw_chain_start + have_tactic.tactic)

            proof = enclose_haves_in_proof(pet, state, have_tactic.proof)
            have_proofs = split_have_proofs(pet, state, previous_goals, proof, qualid_name + '_have_' + str(idx+1), global_variables)

            for st, qn, lm, rlm, pf in have_proofs:
                have_theorem = {"filepath": theorem["filepath"], "statement": lm, "raw_statement": rlm, "proof": pf}
                try:
                    evaluated_theorems = evaluate_theorem(pet, st, qn, have_theorem, dictionary)
                    have_theorems += evaluated_theorems
                except PetanqueError as err:
                    print("QUALID NAME:", qn)
                    print("LEMMA:", lm)
                    print("ERROR:", err.message)

            state = pet.run(state, have_tactic.proof + "." + raw_chain_end)

        else:
            dependencies = find_dependencies(pet, state, raw_chain, known_dependencies)
            dependencies = format_dependencies(pet, state, dependencies, theorem["filepath"], search_dictionary, dictionary["objects"])
            state = pet.run(state, raw_chain)

        known_dependencies += [dependency["name"] for dependency in dependencies]

        new_goals = pet.goals(state)
        goal_diff = goal_lists_diff(previous_goals, new_goals)
        previous_goals = new_goals

        evaluation.append({"chain": raw_chain, "dependencies": dependencies, "goals": list(map(lambda g: g.pp, new_goals)), "goal_diff": goal_diff})

    new_theorem = {
        "statement": theorem["statement"],
        "statement_dependencies": sttt_dependencies,
        "statement_notations": sttt_notations,
        "global_variables": global_variables,
        "initial_goal": initial_goal.pp,
        "evaluation": evaluation
    }
    if "raw_statement" in theorem:
        new_theorem["raw_statement"] = theorem["raw_statement"]

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

        except Exception as err:
            print("Exception:", qualid_name, "\n->", str(err.args[0]))
        except PetanqueError as err:
            print("Petanque:", qualid_name, "\n->", err.message)

    stop_pet_server(pet_server)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate a dataset of Rocq theorems by replaying the proof chain by chain.")
    parser.add_argument("--input", type=str, default="export/output/steps/step_3/mathcomp.json", help="Path of the output of the previous step")
    parser.add_argument("--output", type=str, default="export/output/steps/step_4/", help="Path of the output of this step")
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

    with open(Path(args.output, f"{Path(args.input).stem}.json"), 'w') as file:
        json.dump(result, file, indent=4)
