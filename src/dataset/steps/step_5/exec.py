import re
import os
import json
import argparse
import requests
import concurrent.futures
from typing import Any

from tqdm import tqdm

from src.dataset.prompts import code_explanation_prompt, proof_explanation_prompt, CoT_creation_prompt

"""
Step 5: Generate synthetic CoT.
"""

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
            "model": "anthropic/claude-sonnet-4", # "openai/o3-pro", #
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

def code_explanation(theorem: dict[str, Any]):
    """Explain the code of a proof given as an evaluation and return an evaluation with those explanations."""
    previous_step = {"goals": [theorem["initial_goal"]]}
    for step in theorem["evaluation"]:

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

def proof_explanation(theorem: dict[str, Any]):
    pe_input = proof_explanation_input(theorem)
    pe_output = open_router_query([{"role": "user", "content": proof_explanation_prompt.format(input=pe_input)}])

    match = re.search(r"## Statement\s*(?P<statement>[\s\S]*?)\s*## Proof\s*(?P<proof>[\s\S]*?)\s*\Z", pe_output)
    if not match:
        raise Exception(f"Error: wrong format for the output of proof explanation: {pe_output}.")
    theorem["statement_description"] = match.group("statement")
    theorem["proof_description"] = match.group("proof")

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

    theorem["CoT"] = cot_output

def make(theorem: dict[str, Any]):
    """Make the chain of thought for a theorem."""

    code_explanation(theorem)
    proof_explanation(theorem)
    CoT(theorem)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compute the chains of thought for a dataset of evaluated theorems.")
    parser.add_argument("--input", type=str, default="export/output/steps/step_4/result.json", help="Path of the input")
    parser.add_argument("--output", type=str, default="export/output/steps/step_5/", help="Path of the output")
    parser.add_argument("--max-workers", type=int, default=8)
    args = parser.parse_args()
    os.makedirs(args.output, exist_ok=True)

    with open(args.input, 'r') as file:
        theorems = json.load(file)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = [executor.submit(make, theorem) for theorem in theorems.values()]
        count = 0
        for _ in tqdm(concurrent.futures.as_completed(futures), desc="Overall progress", position=0, total=len(futures)):
            count += 1
            if count % 50 == 0:
                count = 0
                with open(os.path.join(args.output, 'result.json'), 'w') as file:
                    json.dump(theorems, file, indent=4)

    with open(os.path.join(args.output, 'result.json'), 'w') as file:
        json.dump(theorems, file, indent=4)
