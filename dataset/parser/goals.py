from typing import Tuple
from pytanque import Goal

# ====================
# Goals diff
# ====================

def list_all_hypotheses(goal: Goal) -> dict[str, str]:
    """List all hypotheses in a goal."""
    all_hyp = {}
    for h in goal.hyps:
        for name in h.names:
            all_hyp[name] = f"{':= ' + h.def_ + ' ' if h.def_ else ''}: {h.ty}"
    return all_hyp

def goals_hypotheses_diff(goal_hyps1: dict[str, str], goal_hyps2: dict[str, str]) -> Tuple[list[str], list[str], list[str], list[str]]:
    """Compute the difference between two goals hypotheses."""
    added = [f"{name} {pp}" for name, pp in goal_hyps2.items() if not name in goal_hyps1]
    modified = [f"{name} {goal_hyps1[name]}\nchanged to\n{name} {pp}" for name, pp in goal_hyps2.items() if name in goal_hyps1 and pp != goal_hyps1[name]]
    removed = [f"{name} {pp}" for name, pp in goal_hyps1.items() if not name in goal_hyps2]
    unchanged = [f"{name} {pp}" for name, pp in goal_hyps2.items() if name in goal_hyps1 and pp == goal_hyps1[name]]
    return added, modified, removed, unchanged

def goals_diff(goal1: Goal, goal2: Goal) -> str:
    """Compute the difference between two goals."""
    goal_hyps1 = list_all_hypotheses(goal1)
    goal_hyps2 = list_all_hypotheses(goal2)
    added, modified, removed, _ = goals_hypotheses_diff(goal_hyps1, goal_hyps2)

    result = []
    if len(added) > 0:
        result.append("Hypotheses added:\n\n" + "\n".join(added))
    if len(modified) > 0:
        result.append("Hypotheses modified:\n\n" + "\n\n".join(modified))
    if len(removed) > 0:
        result.append("Hypotheses removed:\n\n" + "\n".join(removed))
    if goal1.ty != goal2.ty:
        result.append(f"The goal\n|-{goal1.ty}\nchanged to\n|-{goal2.ty}")

    return "\n\n".join(result)

def goal_lists_diff(goal_list1: list[Goal], goal_list2: list[Goal]) -> str:
    """Compute the difference between two lists of goals,
    considering the second list is obtained by applying a tactic on the first list."""
    added = []
    modified = []
    removed = []
    if len(goal_list2) > len(goal_list1):
        added = list(map(lambda g: g.pp, goal_list2[:len(goal_list2)-len(goal_list1)]))
        goal_list2 = goal_list2[len(goal_list2)-len(goal_list1):] if len(goal_list1) > 0 else []
    elif len(goal_list2) < len(goal_list1):
        removed = list(map(lambda g: g.pp, goal_list1[:len(goal_list1)-len(goal_list2)]))
        goal_list1 = goal_list1[len(goal_list1)-len(goal_list2):] if len(goal_list2) > 0 else []

    for goal1, goal2 in zip(goal_list1, goal_list2):
        diff = goals_diff(goal1, goal2)
        if len(diff) > 0:
            modified.append(diff)

    sep1 = "\n---------------\n"
    sep2 = "\n\n==============================\n\n"
    result = []
    if len(added) > 0:
        result.append("Goals added:\n\n" + sep1.join(added))
    if len(modified) > 0:
        result.append("Goals modified:\n\n" + sep1.join(modified))
    if len(removed) > 0:
        result.append("Goals removed:\n\n" + sep1.join(removed))

    return sep2.join(result)

# ====================
# Testing
# ====================

import json
from pytanque import Pytanque
from .chains import proof_to_raw_chain_list

if __name__ == "__main__":

    with open("math-comp.json", "r") as f:
        data = json.load(f)

    pet = Pytanque("127.0.0.1", 8765)
    pet.connect()

    theorem = "mx_faithful_inj"
    path = "math-comp/" + data[theorem]["filepath"]
    proof = data[theorem]["proof"]
    raw_chain_list = proof_to_raw_chain_list(proof)

    state = pet.start(path, theorem)

    goals = pet.goals(state)
    for raw_chain in raw_chain_list:
        print("##############################")
        print(raw_chain)
        print("##############################\n")
        state = pet.run_tac(state, raw_chain)
        new_goals = pet.goals(state)
        print(goal_lists_diff(goals, new_goals), end="\n\n")
        input()
        goals = new_goals
