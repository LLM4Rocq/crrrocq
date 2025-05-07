import json
import re
from pathlib import Path

def get_global_premises(constants: list[str]) -> dict[str, str]:
    return {d.split(':')[0].strip():":".join(d.split(':')[1:]) for d in constants}

def get_tactic_premises(premises: dict[str, str], tac:str) -> list[str]:
    tokens = set(re.findall(r'\b\w+\b', tac))
    return [word for word in premises.keys() if word in tokens and len(word) > 1]

def trace(data: dict) -> str:
    res = []
    premises = get_global_premises(data['constants'])
    for g_before, step in zip(data['goals'], data['evaluation']):
        tac = step['tactic']
        p = get_tactic_premises(premises, tac)

        res.append("<goals>")
        for i, g in enumerate(g_before):
            res.append(f"Goal {i}")
            res.append(g)
        res.append("</goals>\n")

        if p:
            res.append(f"SEARCH {" ".join(p)}\n")
            
            res.append("<result>")
            for p in p:
                res.append(f"{p}: {premises[p]}\n")
            res.append("</result>")

        res.append("<tactic>")
        res.append(step['tactic'])
        res.append("</tactics>\n")
    return "\n".join(res)

from zero_shot import prompt as zero_shot

def zero_shot_prompt(path: str) -> str:
    p = Path(path)
    with open(path, 'r') as f:
        data = json.load(f)
    return zero_shot + trace(data)

from multi_shot import prompt as multi_shot

def multi_shot_prompt(path: str) -> str:
    p = Path(path)
    with open(path, 'r') as f:
        data = json.load(f)
    return multi_shot + trace(data)

