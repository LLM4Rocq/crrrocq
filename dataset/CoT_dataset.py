import re
import os
import json
import argparse
import requests
import concurrent.futures
from pathlib import Path
from typing import Any, Optional
from tqdm import tqdm

from prompts import code_explanation_prompt, proof_explanation_prompt, CoT_creation_prompt
from prompt.create_CoT import creation_prompt
from prompt.correct_CoT import correction_prompt

# ====================
# Utils
# ====================

def dependency_to_str(dependency: dict[str, str]) -> str:
    """Format a dependency for a CoT input."""
    str_dep = dependency["name"].strip() + " : " + dependency["type"].strip()
    if "info" in dependency:
        str_dep += '\n' + dependency["info"]["docstring"]
    return str_dep

def is_proof_keyword(text: str) -> bool:
    """Return True if the text corresponds to a proof keyword: Proof, Qed or Defined."""
    return bool(re.search(r"(Proof|Qed|Defined)\.", text.strip()))

def open_router_query(messages: list[dict[str, str]]) -> str:
    """A query to open router."""
    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {os.getenv("OPENROUTER_API_KEY")}"},
        data=json.dumps({
            "model": "openai/o3-pro", # "anthropic/claude-sonnet-4",
            "messages": messages
        })
    )
    response = response.json()

    if "error" in response:
        raise Exception(f"Error: open router sent\n{json.dumps(response["error"], indent=2)}")
    return response["choices"][0]["message"]["content"]

# ====================
# Code explanation
# ====================

def step_code_explanation_input(previous_step: dict[str, Any], step: dict[str, Any]) -> str:
    """Explain the code of some step in the proof."""
    input_ = "Goal:\n" + previous_step["goals"][0] + "\n\n"
    input_ += "Tactic:\n" + step["chain"].strip() + "\n\n"
    if len(step["dependencies"]) == 0:
        input_ += "No dependency."
    elif len(step["dependencies"]) == 1:
        input_ += "Dependency:\n" + dependency_to_str(step["dependencies"][0])
    else:
        input_ += "Dependencies:\n" + "\n\n".join(map(dependency_to_str, step["dependencies"]))
    return input_

def code_explanation(initial_goal: str, evaluation: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Explain the code of a proof given as an evaluation and return an evaluation with those explanations."""
    previous_step = {"goals": [initial_goal]}
    for step in evaluation:

        if not is_proof_keyword(step["chain"]):
            ce_input = step_code_explanation_input(previous_step, step)
            ce_output = open_router_query([{"role": "user", "content": code_explanation_prompt.format(input=ce_input)}])

            match = re.search(r"## Breaking it down:\s*(?P<detail>[\s\S]*?)\s*## What happens:\s*(?P<scenario>[\s\S]*?)\s*## Summary:\s*(?P<summary>[\s\S]*?)\s*\Z", ce_output)
            if not match:
                raise Exception(f"Error: wrong format for the output of code explanations: {ce_output}.")
            step["detail"]   = match.group("detail")
            step["scenario"] = match.group("scenario")
            step["summary"]  = match.group("summary")

        previous_step = step

    return evaluation

# ====================
# Proof explanation
# ====================

def step_proof_explanation_input(step: dict[str, Any]) -> str:
    input_ = "<code>\n" + step["chain"].strip() + "\n</code>"
    if len(step["dependencies"]) > 0:
        input_ += "\n<dependencies>\n" + "\n\n".join(map(dependency_to_str, step["dependencies"])) + "\n</dependencies>"
    if "summary" in step:
        input_ += "\n<summary>\n" + step["summary"] + "\n</summary>"
    if len(step["goal_diff"]) > 0:
        input_ += "\n<goal_diff>\n" + step["goal_diff"] + "\n</goal_diff>"
    return "<tactic>\n" + input_ + "\n</tactic>"

def proof_explanation_input(theorem: dict[str, Any]) -> str:
    input_ = "<statement>\n" + theorem["statement"] + "\n</statement>\n\n"
    input_ += "<initial_goal>\n" + theorem["initial_goal"] + "\n</initial_goal>\n\n"
    input_ += "<proof>\n\n" + "\n\n".join(map(step_proof_explanation_input, theorem["evaluation"])) + "\n\n</proof>"
    return input_

def proof_explanation(theorem: dict[str, Any]) -> dict[str, Any]:
    pe_input = proof_explanation_input(theorem)
    pe_output = open_router_query([{"role": "user", "content": proof_explanation_prompt.format(input=pe_input)}])

    match = re.search(r"## Statement\s*(?P<statement>[\s\S]*?)\s*## Proof\s*(?P<proof>[\s\S]*?)\s*\Z", pe_output)
    if not match:
        raise Exception(f"Error: wrong format for the output of proof explanation: {pe_output}.")
    theorem["statement_description"] = match.group("statement")
    theorem["proof_description"] = match.group("proof")

    return theorem

# ====================
# Chain of thought
# ====================

def CoT_step_input(step: dict[str, Any]) -> str:
    input_ = "<code>\n" + step["chain"].strip() + "\n</code>"
    if len(step["dependencies"]) > 0:
        input_ += "\n<dependencies>\n" + "\n\n".join(map(dependency_to_str, step["dependencies"])) + "\n</dependencies>"
    if "detail" in step:
        input_ += "\n<detail>\n" + step["detail"] + "\n</detail>"
    if len(step["goal_diff"]) > 0:
        input_ += "\n<goal_diff>\n" + step["goal_diff"] + "\n</goal_diff>"
    return "<tactic>\n" + input_ + "\n</tactic>"

# TODO: What to do with the statement dependencies ?

def CoT_input(theorem: dict[str, Any]) -> str:
    input_ = "<statement>\n" + theorem["statement"] + "\n</statement>\n\n"
    input_ += "<statement_description>\n" + theorem["statement_description"] + "\n</statement_description>\n\n"
    input_ += "<initial_goal>\n" + theorem["initial_goal"] + "\n</initial goal>\n\n"
    evaluation = [step for step in theorem["evaluation"] if not is_proof_keyword(step["chain"])]
    input_ += "<proof>\n\n" + "\n\n".join(map(CoT_step_input, evaluation)) + "\n\n</proof>\n\n"
    input_ += "<proof_description>\n" + theorem["proof_description"] + "\n</proof_description>"
    return input_

def CoT(theorem: dict[str, Any]) -> str:
    cot_input = CoT_input(theorem)
    cot_output = open_router_query([{"role": "user", "content": CoT_creation_prompt.format(input=cot_input)}])

    return cot_input, cot_output

def make(dataset: str, max_workers: int):
    """Make the chain of thought dataset."""

    datafile = Path(dataset)
    dataset = dataset.split("_", maxsplit=1)[0]
    if not datafile.exists():
        raise Exception(f"Error: {datafile} doesn't exists.")
    savefile = Path(datafile.parent, datafile.stem + "_CoT.json")

    # if savefile.exists():
    #     print("Dataset of chains of thought already here.")
    # else:
    print("Making the chains of thought.")

    print("  Reading the data ...")
    with open(datafile, "r") as f:
        theorems = json.load(f)

    print("  Computing the code explanations ...")
    for qualid_name in theorems.keys():
        theorems[qualid_name]["evaluation"] = code_explanation(theorems[qualid_name]["initial_goal"], theorems[qualid_name]["evaluation"])

    print("  Computing the proof explanation ...")
    for qualid_name in theorems.keys():
        theorems[qualid_name] = proof_explanation(theorems[qualid_name])
    res1 = list(theorems.values())[0]

    print("  Computing the chains of thought ...")
    for qualid_name in theorems.keys():
        theorems[qualid_name] = CoT(theorems[qualid_name])
    res2, res3 = list(theorems.values())[0]

    # print("  Computing the inputs for chains of thought ...")
    # theorems = {qualid_name: make_CoT_input(theorem) for qualid_name, theorem in theorems.items()}

    # print("  Computing the chains of thought ...")
    # with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
    #     futures = [executor.submit(lambda qn, t: (qn, make_CoT(t)), qualid_name, theorem) for qualid_name, theorem in theorems.items()]
    #     for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures)):
    #         qualid_name, theorem = future.result()
    #         theorems[qualid_name] = theorem

    # print("  Saving the chains of thought ...")
    # with open(savefile, "w") as f:
    #     json.dump(theorems, f, indent = 2)

    with open(savefile, "w") as f:
        json.dump({"theorem": res1, "input": res2, "output": res3}, f, indent=2)

    print("DONE!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compute the chains of thought associated to a dataset of evaluated theorems.")
    parser.add_argument("--dataset", type=str, default="algebra_one_CoT.json", help="The path of the dataset, default is 'mathcomp_bm25_have_1000_0.5_first_19-20th_eval.json'")
    parser.add_argument("--max_workers", type=int, default=10, help="The number of maximum workers when launching requests to Anthropic, default is 10")
    args = parser.parse_args()
    make(args.dataset, args.max_workers)
