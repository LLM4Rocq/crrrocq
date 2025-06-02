import re
import json
import argparse
from pathlib import Path
from typing import Any, Optional
from tqdm import tqdm

def make_CoT_input_dependency(dependency: dict[str, str]) -> str:
    """Format a dependency for a CoT input."""
    str_dep = dependency["name"].strip() + " : " + dependency["type"].strip()
    if "info" in dependency:
        str_dep += '\n' + dependency["info"]["docstring"]
    return str_dep

def make_CoT_input_step(step: dict[str, Any]) -> Optional[str]:
    """Make one step of a the CoT input."""

    chain = step["chain"].strip()
    if not re.search(r"(Proof|Qed|Defined)\.", chain):
        str_step = "<chain>\n" + chain + "\n</chain>\n"
        if len(step["dependencies"]) > 0:
            str_step += "<dependencies>\n" + "\n\n".join(map(make_CoT_input_dependency, step["dependencies"])) + "\n</dependencies>\n"
        str_step += "<goal diff>\n" + step["goal_diff"] + "\n</goal diff>"
        return str_step

    else:
        return None

def make_CoT_input(theorem: dict[str, Any]) -> str:
    """Make the CoT input out of the statement and the evaluation of a theorem."""

    CoT_input = "<theorem>\n" + theorem["statement"] + "\n</theorem>\n\n"
    CoT_input += "<initial goal>\n" + theorem["initial_goal"] + "\n</initial goal>\n\n"
    evaluation = map(make_CoT_input_step, theorem["evaluation"])
    evaluation = [step for step in evaluation if step]
    CoT_input += "<proof>\n\n" + "\n\n".join(evaluation) + "\n\n</proof>"

    return CoT_input

def make(dataset: str):
    """Make the chain of thought dataset."""

    datafile = Path(dataset)
    dataset = dataset.split("_", maxsplit=1)[0]
    if not datafile.exists():
        raise Exception(f"Error: {datafile} doesn't exists.")
    savefile = Path(datafile.parent, datafile.stem + "_CoT.json")
    if not savefile.exists():
        with open(savefile, "w") as f:
            f.write("{}")

    print("Making the chains of thought.")

    print("  Reading the data ...")
    with open(datafile, "r") as f:
        theorems = json.load(f)

    with open(savefile, "r") as f:
        CoT_theorems = json.load(f)

    non_CoT_theorems = {qualid_name: theorem for qualid_name, theorem in theorems.items() if not qualid_name in CoT_theorems}

    print("  Computing the chains of thought ...")
    non_CoT_theorems = {qualid_name: make_CoT_input(theorem) for qualid_name, theorem in tqdm(non_CoT_theorems.items())}

    print("  Saving the chains of thought ...")
    with open(savefile, "w") as f:
        json.dump(CoT_theorems | non_CoT_theorems, f, indent = 2)

    print("DONE!")

# TODO: know what to do with initial goals and statement dependencies

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compute the chains of thought associated to a dataset of evaluated theorems.")
    parser.add_argument("--dataset", type=str, default="mathcomp_bm25_have_1000_0.5_first_19-20th_eval.json", help="The path of the dataset, default is 'mathcomp_bm25_have_1000_0.5_first_19-20th_eval.json'")
    args = parser.parse_args()
    make(args.dataset)
