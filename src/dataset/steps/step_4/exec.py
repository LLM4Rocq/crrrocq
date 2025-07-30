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
from src.parser.chains import proof_to_raw_chain_list
from src.parser.goals import goal_lists_diff, goal_to_lemma, pp_hypothesis, remove_global_variables

"""
Step 4: Evaluate all theorems (goals, dependencies, etc.).
"""

# ====================
# Utils
# ====================

def quick_pp_hypothesis(hyp) -> str:
    """Pretty print a hypothesis."""
    return pp_hypothesis(hyp.names, hyp.def_, hyp.ty)

def load_dictionary(dfile: str) -> dict:
    """Load the dictionary."""

    with open(dfile, 'r') as file:
        d_base = json.load(file)

    d = {"objects": {}, "notations": d_base["notations"]}

    for object in d_base["objects"]:
        for key in object["keys"]:
            d["objects"][key] = object["value"]

    return d

# ====================
# Notations
# ====================

def notations_list_to_notations_dict(not_list: list[str]) -> dict[str, Any]:
    """Transform a list of notations into a dict of notations."""

    not_dict = {"scope": {}, "noscope": {}}
    for cnot in not_list:
        qualid_name = cnot["path"] + ('.' + cnot["secpath"] if cnot["secpath"] != "<>" else "") + '.' + cnot["notation"]
        if cnot["scope"]:
            if not cnot["scope"] in not_dict["scope"]:
                not_dict["scope"][cnot["scope"]] = {}
            d = not_dict["scope"][cnot["scope"]]
        else:
            d = not_dict["noscope"]

        d[qualid_name] = {"name": cnot["notation"]}

    return not_dict

def find_notations_in_hypothesis(pet: Pytanque, state: State, hypothesis_typ: str, bad: list) -> list:
    """Find all notations appearing in the hypothesis."""
    notations = pet.list_notations_in_statement(state, "Lemma notations_in_hypothesis : " + hypothesis_typ + ".")
    return [notation for notation in notations if not notation in bad]

def find_notations_in_statement(pet: Pytanque, state: State, statement: str, bad: list) -> list:
    """Find all notations appearing in the statement."""
    notations = pet.list_notations_in_statement(state, "Lemma notations_in_statement : " + statement + ".")
    return [notation for notation in notations if not notation in bad]

def format_notations(pet: Pytanque, state: State, notations_list: list, filepath: str, dictionary: dict[str, str]) -> list:
    """Format notations."""

    filepath = Path(filepath)
    filename = filepath.stem

    notations_dict = notations_list_to_notations_dict(notations_list)
    new_notations_dict = {"scope": {scope: {} for scope in notations_dict["scope"]}, "noscope": {}}

    # Iter over notations with scope and notations without scope
    all_notations = []
    for scope, scope_notations in notations_dict["scope"].items():
        if scope in dictionary["scope"]:
            all_notations.append((new_notations_dict["scope"][scope], scope_notations, dictionary["scope"][scope]))
    all_notations.append((new_notations_dict["noscope"], notations_dict["noscope"], dictionary["noscope"]))

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
                # print("NOTATION:", qname)
            elif len(dntns) > 1:
                pass
                # print("NOTATIONS:", dntns)
            else:
                qname = dntns[0]
                save_notations[qname] = notation | {"info": dictionary[qname]}

    return new_notations_dict

# ====================
# Dependencies
# ====================

def find_dependencies_in_tactic(pet: Pytanque, state: State, code: str, bad: list[str]) -> list[str]:
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

def find_dependencies_in_hypothesis(pet: Pytanque, state: State, hypothesis: str, bad: list[str]) -> list[str]:
    """Find all dependencies in the hypothesis."""
    lemma = "Variable " + hypothesis + "."
    ast = pet.ast(state, lemma)
    dependencies = list_dependencies(ast)
    return [dependency for dependency in dependencies if not dependency in bad]

def find_dependencies_in_statement(pet: Pytanque, state: State, statement: str, bad: str) -> list[str]:
    """Find all dependencies in the statement."""
    lemma = "Goal " + statement + "."
    ast = pet.ast(state, lemma)
    dependencies = list_dependencies(ast)
    return [dependency for dependency in dependencies if not dependency in bad]

def format_dependency(pet: Pytanque, state: State, dependency: str, filepath: str, type_dictionary: dict[str, str], info_dictionary: dict[str, Any]) -> Optional[dict[str, str]]:
    """Format a dependency."""

    state = pet.run(state, f"Locate Term {dependency}.")
    message = state.feedback[0][1]

    # Check if the dependency is syntactically equal to another theorem
    match = re.search(r"(Constant|Inductive|Constructor)\s*(?P<first_qualid_name>\S*)\s*\(syntactically\s*equal\s*to\s*(?P<second_qualid_name>\S*)\s*\)", message)
    if match and match.start() == 0:
        qualid_names = [match.group("first_qualid_name"), match.group("second_qualid_name")]

    else:
        # Check for normal dependency
        match = re.search(r"(Constant|Inductive|Constructor)\s*(?P<qualid_name>\S*)", message)
        if match and match.start() == 0:
            qualid_names = [match.group("qualid_name")]

        else:
            # Check for notation dependency
            match = re.search(r"Notation\s*(?P<qualid_name>\S*)", message)
            if match and match.start() == 0:
                qualid_names = [match.group("qualid_name")]

            else:
                return None

    res = {"name": dependency}
    if dependency in type_dictionary:
        res["type"] = type_dictionary[dependency]

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
        pass
        # print("INFO, QUALID NAMES:", qualid_names)
    if not "type" in res:
        pass
        # state = pet.run(state, f"Check {dependency}.")
        # message = state.feedback[0][1]
        # match = re.search(f"{dependency}\\s*?:\\s(?P<type>[\\s\\S]*)", message)
        # res["type"] = match.group("type").strip()

    return res

def format_dependencies(pet: Pytanque, state: State, dependencies: list[str], filepath: str, type_dictionary: dict[str, str], info_dictionary: dict[str, Any]) -> list[dict[str, str]]:
    """Format dependencies."""
    dependencies = [format_dependency(pet, state, dependency, filepath, type_dictionary, info_dictionary) for dependency in dependencies]
    return [dependency for dependency in dependencies if dependency]

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
    all_dependencies = []
    all_notations = []

    # Compute the notations and dependencies in global variables
    for hyp in global_variables:
        global_variables_names += hyp.names
        all_dependencies += hyp.names
        hyp_str = quick_pp_hypothesis(hyp)

        notations = find_notations_in_hypothesis(pet, state, hyp.ty, all_notations)
        all_notations += notations
        notations = format_notations(pet, state, notations, theorem["filepath"], dictionary["notations"])

        dependencies = find_dependencies_in_hypothesis(pet, state, hyp_str, all_dependencies)
        all_dependencies += dependencies
        dependencies = format_dependencies(pet, state, dependencies, theorem["filepath"], type_dictionary, dictionary["objects"])

        formatted_global_variables.append({
            "pp": "Variables " + hyp_str[1:-1] + ".",
            "notations": notations,
            "dependencies": dependencies
        })

    # Compute the initial goal
    initial_goals = pet.goals(state)
    if len(initial_goals) != 1:
        raise Exception(f"Error: {qualid_name} starts with a number of goals different from one.")
    initial_goal = initial_goals[0]
    initial_goal = remove_global_variables(initial_goal, global_variables_names)
    raw_initial_goal = pet.goals(pet.run(state, "Set Printing All."))[0]
    raw_initial_goal = remove_global_variables(raw_initial_goal, global_variables_names)

    # Compute the statement's notations
    sttt_notations = []
    var_state = state

    for hyp, raw_hyp in zip(initial_goal.hyps, raw_initial_goal.hyps):
        names = [name for name in hyp.names if not name in global_variables_names]

        if len(names) > 0:
            raw_hyp_str = pp_hypothesis(names, raw_hyp.def_, raw_hyp.ty)
            var_state = pet.run(var_state, f"Variable {raw_hyp_str}.")

            try:
                notations = find_notations_in_hypothesis(pet, var_state, hyp.ty, all_notations)
                all_notations += notations
                sttt_notations += notations
            except PetanqueError as err:
                pass

    if "exact_statement" in theorem:
        statement_str = theorem["exact_statement"]
    else:
        statement_str = initial_goal.ty
    sttt_notations += find_notations_in_statement(pet, var_state, initial_goal.ty, all_notations)
    sttt_notations = format_notations(pet, state, sttt_notations, theorem["filepath"], dictionary["notations"])

    # Compute the statement's dependencies
    sttt_dependencies = []

    for hyp in initial_goal.hyps:
        hyp_str = pp_hypothesis(hyp.names, hyp.def_, hyp.ty)
        dependencies = find_dependencies_in_hypothesis(pet, state, hyp_str, all_dependencies)
        all_dependencies += dependencies
        sttt_dependencies += dependencies

    dependencies = find_dependencies_in_statement(pet, state, initial_goal.ty, all_dependencies)
    all_dependencies += dependencies
    sttt_dependencies += dependencies
    sttt_dependencies = format_dependencies(pet, state, sttt_dependencies, theorem["filepath"], type_dictionary, dictionary["objects"])

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

            dependencies = find_dependencies_in_tactic(pet, state, raw_chain_start + have_tactic.tactic, all_dependencies)
            all_dependencies += dependencies
            dependencies = format_dependencies(pet, state, dependencies, theorem["filepath"], type_dictionary, dictionary["objects"])

            state = pet.run(state, raw_chain_start + have_tactic.tactic)

            proof = enclose_haves_in_proof(pet, state, have_tactic.proof)
            have_qualid_name = qualid_name + '_have_' + str(idx+1)
            have_theorem = {"filepath": theorem["filepath"], "proof": proof, "excat_statement": have_tactic.get_statement()}
            try:
                have_state = format_have_tactic(pet, state, have_qualid_name, global_variables_names)
                evaluated_theorems = evaluate_theorem(pet, have_state, have_qualid_name, have_theorem, dictionary)
                have_theorems += evaluated_theorems
            except PetanqueError as err:
                pass

            state = pet.run(state, have_tactic.proof + "." + raw_chain_end)

        else:
            dependencies = find_dependencies_in_tactic(pet, state, raw_chain, all_dependencies)
            all_dependencies += dependencies
            dependencies = format_dependencies(pet, state, dependencies, theorem["filepath"], type_dictionary, dictionary["objects"])
            state = pet.run(state, raw_chain)

        new_goals = pet.goals(state)
        new_goals = list(map(lambda g: remove_global_variables(g, global_variables_names), new_goals))
        goal_diff = goal_lists_diff(previous_goals, new_goals)
        previous_goals = new_goals

        evaluation.append({"chain": raw_chain, "dependencies": dependencies, "goals": list(map(lambda g: g.pp, new_goals)), "goal_diff": goal_diff})

    new_theorem = {
        "global_variables": formatted_global_variables,
        "initial_goal": initial_goal.pp,
        "statement_dependencies": sttt_dependencies,
        "statement_notations": sttt_notations,
        "evaluation": evaluation
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
            pass
            print("Petanque:", qualid_name, "\n->", err.message)
        except Exception as err:
            pass
            print("Exception:", qualid_name, "\n->", str(err.args[0]))

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

    make(to_do["mathcomp/solvable/abelian.v"], dictionary, 8765)

    # with concurrent.futures.ProcessPoolExecutor(max_workers=args.max_workers) as executor:
    #     futures = []
    #     for k, source in enumerate(to_do):
    #         futures.append(executor.submit(make, to_do[source], dictionary, 8765 + k))
    #     for _ in tqdm(concurrent.futures.as_completed(futures), desc="Overall progress", position=0, total=len(futures)):
    #         pass

    result = {}
    for filepath in aux_path.iterdir():
        with open(filepath, 'r') as file:
            content = json.load(file)
        result = result | content

    with open(Path(args.output, f"{Path(args.input).stem}.json"), 'w') as file:
        json.dump(result, file, indent=4)
