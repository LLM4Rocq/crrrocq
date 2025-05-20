import re
import json
import argparse
from typing import Any
from pytanque import Pytanque, State
from pathlib import Path
from tqdm import tqdm

from parser.haves import HaveTactic, parse_have_tags, parse_have_tactics
from parser.chains import proof_to_raw_chain_list
from parser.goals import goal_lists_diff

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

def find_dependencies(code: str, bad_names: list[str], valid_names: list[str]) -> list[str]:
    """Find all occurrences of `valid_names` in `code`, provided `bad_names` to not take into account."""
    pattern = re.compile(r"(?P<name>[_'a-zA-Z0-9]*)")
    all_names = [match.group("name") for match in pattern.finditer(code)]
    bad_names = rocq_keywords + bad_names
    all_names_except_bad = [n for n in all_names if not n in bad_names]
    all_valid_names = [n for n in all_names_except_bad if n in valid_names]
    return all_valid_names

def find_global_variables(pet: Pytanque, state: State) -> list[str]:
    """Retrieve the global variable present at state `state`."""
    state = pet.run_tac(state, "Goal true = true.")
    goal = pet.goals(state)[0]
    global_variables = []
    for hyp in goal.hyps:
        global_variables += hyp.names
    return global_variables

def evaluate_theorem(dataset: str, pet: Pytanque, theorem: dict[str, Any], valid_names: list[str]) -> dict[str, Any]:
    """Evaluate a theorem's proof."""

    # print("NAME:", theorem["name"])

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

    have_tactics = list(filter(lambda s: isinstance(s, HaveTactic), parsed_proof))
    assert (len(have_tactics) == have_idx)

    raw_chain_list = proof_to_raw_chain_list(skeleton_proof)

    state = pet.start(Path(dataset, theorem["filepath"]), theorem["name"])

    # Compute the global variables
    global_variables = find_global_variables(pet, state)

    previous_goals = pet.goals(state)
    evaluation = [previous_goals[0].pp]
    for raw_chain in raw_chain_list:
        dependencies = find_dependencies(raw_chain, global_variables, valid_names)

        # If there is some have tactic in the raw chain, expend it
        match = parse_have_tags(raw_chain)
        str_raw_chain = ""
        run_raw_chain = ""

        while match:
            str_raw_chain += raw_chain[:match.start()]
            run_raw_chain += raw_chain[:match.start()]
            have_tactic = have_tactics[int(match.group("body"))]
            str_raw_chain += have_tactic.no_proof()
            run_raw_chain += str(have_tactic)
            raw_chain = raw_chain[match.end():]
            match = parse_have_tags(raw_chain)

        str_raw_chain += raw_chain
        run_raw_chain += raw_chain

        # print("STR RAW CHAIN:", str_raw_chain)
        # print("RUN RAW CHAIN:", run_raw_chain)

        evaluation.append({"tactic": str_raw_chain, "dependencies": dependencies})

        state = pet.run_tac(state, run_raw_chain)
        new_goals = pet.goals(state)
        evaluation.append(goal_lists_diff(previous_goals, new_goals))
        previous_goals = new_goals

    return {
        "name": theorem["name"],
        "statement": theorem["statement"],
        "statement_dependencies": find_dependencies(theorem["statement"], [theorem["name"]], valid_names),
        "proof": theorem["proof"],
        "global_variables": global_variables,
        "evaluation": evaluation
    }

def make(dataset: str, complet_dataset: str, petanque_address: str, petanque_port: int):
    """Compute the evaluation of all theorems in the dataset."""

    datafile = Path(dataset)
    dataset = dataset.split("_", maxsplit=1)[0]
    if not datafile.exists():
        raise Exception(f"Error: {datafile} doesn't exists.")
    complet_datafile = Path(complet_dataset)
    if not complet_datafile.exists():
        raise Exception(f"Error: {complet_dataset} doesn't exists.")
    savefile = Path(datafile.parent, datafile.stem + "_eval.jsonl")

    if savefile.exists():
        print("Evaluated dataset already here.")
    else:

        print("Making the evaluated dataset.")

        print("  Connecting to petanque ...")
        pet = Pytanque(petanque_address, petanque_port)
        pet.connect()

        print("  Reading the data ...")
        theorems = []
        with open(datafile, "r") as f:
            for line in f:
                theorems.append(json.loads(line))

        print("  Retrieving all valid names ...")
        valid_names = []
        with open(complet_datafile, "r") as f:
            for line in f:
                theorem = json.loads(line)
                valid_names.append(theorem["name"])

        print("  Computing evaluations ...")
        evaluated_theorems = []
        for theorem in tqdm(theorems):
            evaluated_theorem = evaluate_theorem(dataset, pet, theorem, valid_names)
            evaluated_theorems.append(evaluated_theorem)

        print("  Saving the data ...")
        with open(savefile, "w") as f:
            for theorem in evaluated_theorems:
                theorem = json.dumps(theorem)
                f.write(theorem + '\n')

        print("  DONE!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate a dataset of Rocq theorems by replaying the proof chain by chain.")
    parser.add_argument("--dataset", type=str, default="math-comp_bm25_have_1000_0.5_first_19-20th.jsonl", help="The path of the dataset, default is 'math-comp_bm25_have_1000_0.5_first_19-20th.jsonl'")
    parser.add_argument("--complet_dataset", type=str, default="math-comp.jsonl", help="The path of the complet dataset, default is 'math-comp.jsonl'")
    parser.add_argument("--address", type=str, default="127.0.0.1", help="Address of the petanque server, default is '127.0.0.1'")
    parser.add_argument("--port", type=int, default=8765, help="Port of the petanque server, default is 8765")
    args = parser.parse_args()
    make(args.dataset, args.complet_dataset, args.address, args.port)
