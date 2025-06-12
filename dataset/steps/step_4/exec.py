import re
import json
import argparse
from typing import Any, Tuple, Dict
from pathlib import Path
from collections import defaultdict
import os
import concurrent.futures

from pytanque import Pytanque, State, Goal
from tqdm import tqdm

from src.training.eval import start_pet_server, stop_pet_server
from dataset.parser.haves import HaveTactic, parse_have_tags, parse_have_tactics, enclose_haves_in_proof
from dataset.parser.chains import proof_to_raw_chain_list, raw_chain_list_to_str
from dataset.parser.goals import goal_lists_diff, replace_list, goal_to_lemma

rocq_keywords = [
    "Lemma",
    "Theorem",
    "Fact",
    "Remark",
    "Corollary",
    "Proposition",
    "Property",
    "Proof",
    "Defined",
    "Qed",
    "have",
    "move",
    "intro",
    "intros",
    "induction",
    "rewrite",
    "by",
    "at",
    "apply"
]

# TODO: better handle `last` case (if at the beginning of a tactic, do not count as a dependency)
# TODO: better handle `{poly _}` case to not yield a dependency with lemma poly

def find_dependencies(code: str, bad_names: list[str], valid_names: list[str]) -> Tuple[list[str], list[str]]:
    """Find all occurrences of `valid_names` in `code`, provided `bad_names` to not take into account."""
    bad_names = rocq_keywords + bad_names
    matches = re.finditer(r"(?P<name>[_'a-zA-Z0-9][_'a-zA-Z0-9\.]*[_'a-zA-Z0-9])", code)
    names = [match.group("name") for match in matches]

    dependencies = []
    for name in names:
        if not name in bad_names and name in valid_names:
            dependencies.append(name)
            bad_names.append(name)

    return dependencies

def find_opened_sections(text: str) -> list[str]:
    """Return the list of opened sections in some text."""
    sections = []
    match = re.search(r"Section\s(?P<name>\S*).", text)

    if match:
        text = text[match.end():]
        section_name = match.group("name")
        section_end = f"End {section_name}."
        close_idx = text.find(section_end)

        if close_idx >= 0:
            text = text[close_idx+len(section_end):]
            return find_opened_sections(text)
        else:
            return [section_name] + find_opened_sections(text)

    else:
        return sections

def find_sections(filepath: str, position: str) -> list[str]:
    """Return the list of sections we are in at a certain position in a file."""

    content = ""
    with open(filepath, "r") as f:
        for i, line in enumerate(f):
            if i < position["line"]:
                content += line
            else:
                content += line[:position["character"]]
                break

    return find_opened_sections(content)

def sublist_index(l1: list, l2: list) -> bool:
    """If the first list is a sublist of the second one, return the last index at which the first list starts in the second list. Else return -1."""
    res = -1
    for i in range(len(l2) - len(l1) + 1):
        if l1 == l2[i:i+len(l1)]:
            res = i
    return res

def format_dependency(pet: Pytanque, state: State, filepath: str, dependency: str, sections: list[str], search_dictionary: dict[str, str], info_dictionary: dict[str, str]) -> dict[str, str]:
    """Format a dependency."""
    state = pet.run(state, f"Locate Term {dependency}.")
    if len(state.feedback) == 0:
        raise Exception(f"Error: there should be at least one feedback when doing `Locate {dependency}.`.")
    message = state.feedback[0][1]

    # Check if the dependency is syntactically equal to another theorem
    match = re.search(r"(Constant|Inductive|Constructor)\s*(?P<first_qualid_name>\S*)\s*\(syntactically\s*equal\s*to\s*(?P<second_qualid_name>\S*)\s*\)", message)
    if match and match.start() == 0:
        qualid_names = [match.group("first_qualid_name"), match.group("second_qualid_name")]
    else:
        match = re.search(r"(Constant|Inductive|Constructor)\s(?P<qualid_name>\S*)", message)
        if not match or match.start() != 0:
            raise Exception(f"Error: not the right format for {message}.")
        qualid_names = [match.group("qualid_name")]

    filepath = Path(filepath)
    filename = filepath.stem
    res = {"name": dependency, "type": search_dictionary[dependency]}

    for qualid_name in qualid_names:
        # Check if the dependency is declared in the same file that the state is in
        if filename == qualid_name.split('.', maxsplit=1)[0]:
            qualid_prefix = '.'.join(filepath.parent.parts)
            qualid_name = qualid_prefix + '.' + qualid_name

        # Remove names that corresponds to the sections we are in
        split_qualid_name = qualid_name.split('.')
        idx = sublist_index(sections, split_qualid_name)
        if idx >= 0:
            qualid_name = '.'.join(split_qualid_name[:idx] + split_qualid_name[idx+len(sections):])

        if qualid_name in info_dictionary:
            res["info"] = info_dictionary[qualid_name]
            break

    return res

def find_global_variables(pet: Pytanque, state: State) -> list[str]:
    """Retrieve the global variable present at state `state`."""
    state = pet.run(state, "Goal true = true.")
    goal = pet.goals(state)[0]
    global_variables = []
    for hyp in goal.hyps:
        global_variables += hyp.names
    return global_variables

def split_have_proofs(pet: Pytanque, state: State, previous_goals: list[Goal], have_statement: str, have_proof: str, qualid_name: str, global_variables: list[str]) -> list[Tuple[State, str, str, str, str]]:
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

def evaluate_theorem(pet: Pytanque, state: State, sections: list[str], qualid_name: str, theorem: dict[str, Any], dictionary: dict[str, Any]) -> dict[str, Any]:
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

    valid_names = list(search_dictionary.keys())

    # Compute the statement's dependencies
    sttt_dependencies = find_dependencies(theorem["statement"], [name] + hypotheses, valid_names)
    sttt_dependencies = [format_dependency(pet, state, theorem["filepath"], dep, sections, search_dictionary, dictionary) for dep in sttt_dependencies]
    known_dependencies = [dep for dep in sttt_dependencies]

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

            state = pet.run(state, raw_chain_start + have_tactic.tactic)

            proof = enclose_haves_in_proof(pet, state, have_tactic.proof)
            have_proofs = split_have_proofs(pet, state, previous_goals, have_tactic.get_statement(), proof, qualid_name + '_have_' + str(idx+1), global_variables)
            for st, qn, lm, rlm, pf in have_proofs:
                have_theorem = {"filepath": theorem["filepath"], "statement": lm, "raw_statement": rlm, "proof": pf}
                evaluated_theorems = evaluate_theorem(pet, st, sections, qn, have_theorem, dictionary)
                have_theorems += evaluated_theorems

            state = pet.run(state, have_tactic.proof + "." + raw_chain_end)

        else:
            state = pet.run(state, raw_chain)

        dependencies = find_dependencies(raw_chain, known_dependencies + hypotheses, valid_names)
        dependencies = [format_dependency(pet, state, theorem["filepath"], dep, sections, search_dictionary, dictionary) for dep in dependencies]
        known_dependencies += dependencies

        new_goals = pet.goals(state)
        goal_diff = goal_lists_diff(previous_goals, new_goals)
        previous_goals = new_goals

        evaluation.append({"chain": raw_chain, "dependencies": dependencies, "goals": list(map(lambda g: g.pp, new_goals)), "goal_diff": goal_diff})

    new_theorem = {
        "statement": theorem["statement"],
        "statement_dependencies": sttt_dependencies,
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
        theorem["fqn"] = qualid_name
        path = theorem["filepath"]
        export_filepath = os.path.join(export_path, 'aux', qualid_name) + '.json'
        if not os.path.exists(export_filepath):
            to_do[path].append((qualid_name, theorem, export_filepath))
    return to_do

def make(theorems: str, dictionary: Dict[str, Any], petanque_port: int):
    """Compute the evaluation of all theorems in the dataset provided the dictionary."""

    pet_server = start_pet_server(petanque_port)
    pet = Pytanque("127.0.0.1", petanque_port)
    pet.connect()
    # count = 0
    for qualid_name, theorem, export_filepath in tqdm(theorems):
        state = pet.get_state_at_pos(theorem["filepath"], theorem["position"]["line"], theorem["position"]["character"], 0)
        sections = find_sections(theorem["filepath"], theorem["position"])
        for qualid_name, evaluated_theorem in evaluate_theorem(pet, state, sections, qualid_name, theorem, dictionary):
            print(qualid_name)
            with open(export_filepath, 'w') as file:
                json.dump(evaluated_theorem, file, indent=4)
        # count += 1
        # if count%1_000==0:
        stop_pet_server(pet_server)
        pet_server = start_pet_server(petanque_port)
    stop_pet_server(pet_server)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate a dataset of Rocq theorems by replaying the proof chain by chain.")
    parser.add_argument("--input", type=str, default="export/output/steps/step_3/result.json", help="Path of the input")
    parser.add_argument("--output", type=str, default="export/output/steps/step_4/", help="Path of the output")
    parser.add_argument("--dictionary", type=str, default="export/docstrings/dictionary.json", help="The path of the dictionary to be used, default is 'dictionary.json'.")
    parser.add_argument("--address", type=str, default="127.0.0.1", help="Address of the petanque server, default is '127.0.0.1'")
    parser.add_argument("--max-workers", type=int, default=8)
    args = parser.parse_args()
    os.makedirs(os.path.join(args.output, 'aux'), exist_ok=True)
    to_do = chunk_dataset(args.input, args.output)

    with open(args.dictionary, 'r') as file:
        dictionary = json.load(file)
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.max_workers) as executor:
        futures = []
        for k, parent in enumerate(to_do):
            futures.append(executor.submit(make, to_do[parent], dictionary, 8765 + k))

        for _ in tqdm(concurrent.futures.as_completed(futures), desc="Overall progress", position=0, total=len(futures)):
            pass
