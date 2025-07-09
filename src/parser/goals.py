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
    modified = [f"{name} changed to {pp}" for name, pp in goal_hyps2.items() if name in goal_hyps1 and pp != goal_hyps1[name]]
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
        result.append("Hypotheses added:\n" + "\n".join(added))
    if len(modified) > 0:
        result.append("Hypotheses modified:\n" + "\n\n".join(modified))
    if len(removed) > 0:
        result.append("Hypotheses removed:\n" + "\n".join(removed))
    if goal1.ty != goal2.ty:
        result.append(f"The goal changed to:\n|-{goal2.ty}")

    return "\n\n".join(result)

def goal_lists_diff(goal_list1: list[Goal], goal_list2: list[Goal]) -> str:
    """Compute the difference between two lists of goals,
    considering the second list is obtained by applying a tactic on the first list."""
    added = []
    modified = []
    removed = 0
    len_diff = len(goal_list2) - len(goal_list1)
    if len_diff > 0:
        added = list(map(lambda g: g.pp, goal_list2[:len_diff]))
        goal_list2 = goal_list2[len_diff:] if len(goal_list1) > 0 else []
    elif len_diff < 0:
        removed = -len_diff
        goal_list1 = goal_list1[-len_diff:] if len(goal_list2) > 0 else []

    for i, (goal1, goal2) in enumerate(zip(goal_list1, goal_list2)):
        diff = goals_diff(goal1, goal2)
        old_pos = max(0, -len_diff) + i
        new_pos = max(0,  len_diff) + i
        if len(diff) > 0:
            if old_pos == new_pos:
                modified.append(f"The goal {old_pos} is changed:\n{diff}")
            else:
                modified.append(f"The goal {old_pos} is changed and is now the goal {new_pos}:\n{diff}")

    sep1 = "\n\n"
    sep2 = "\n\n"
    result = []
    if removed > 0:
        if removed == 1:
            result.append(f"1 goal has been removed.")
        else:
            result.append(f"{removed} goals have been removed.")
        if len(goal_list2) > 0:
            result[-1] += f"\nThe new goal to prove is:\n{goal_list2[-1].pp}"
        else:
            result[-1] += "\nThere is no goal remaining, the proof is finished."
    elif len(added) > 0:
        result.append("Goals added:\n\n" + sep1.join(added))
    if len(modified) > 0:
        result.append("Goals modified:\n\n" + sep1.join(modified))

    return sep2.join(result)

# ====================
# Lemma correspondence
# ====================

def replace_list(text: str, replace_list: list[Tuple[str, str]]) -> str:
    """Apply replace consecutively on some text with a list of old and new strings provided."""
    for old, new in replace_list:
        text = text.replace(old, new)
    return text

def goal_to_lemma(goal: Goal, name: str, global_variables: list[str]) -> Tuple[list[Tuple[str, str]], str]:
    """Return a string containing a lemma version of some goal."""
    renamed = []
    lemma = f"Lemma {name}"

    for hyp in goal.hyps:
        names = [name for name in hyp.names if not name in global_variables]

        # Variables named `_?_` are not possible to write as lemmas arguments
        for i, name in enumerate(names):
            if name[0] == '_' and name[-1] == '_':
                new_name = name[1:]
                renamed.append((name, new_name))
                names[i] = new_name

        if len(names) > 0:
            lemma += " (" + " ".join(names) + (" := (" + replace_list(hyp.def_, renamed) + ")" if hyp.def_ else "") + " : " + replace_list(hyp.ty, renamed) + ")"

    lemma += " : " + replace_list(goal.ty, renamed) + "."
    return renamed, lemma

def goal_to_lemma_def(goal: Goal, name: str, global_variables: list[str]) -> Tuple[list[Tuple[str, str]], str]:
    """Return a string containing a lemma version of some goal. If some hypotheses have a definition, their type is not written."""
    renamed = []
    lemma = f"Lemma {name}"

    for hyp in goal.hyps:
        names = [name for name in hyp.names if not name in global_variables]

        # Variables named `_?_` are not possible to write as lemmas arguments
        for i, name in enumerate(names):
            if name[0] == '_' and name[-1] == '_':
                new_name = name[1:]
                renamed.append((name, new_name))
                names[i] = new_name

        if len(names) > 0:
            lemma += " (" + " ".join(names) + (" := (" + replace_list(hyp.def_, renamed) + ")" if hyp.def_ else " : " + replace_list(hyp.ty, renamed)) + ")"

    lemma += " : " + replace_list(goal.ty, renamed) + "."
    return renamed, lemma

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
        state = pet.run(state, raw_chain)
        new_goals = pet.goals(state)
        print(goal_lists_diff(goals, new_goals), end="\n\n")
        input()
        goals = new_goals
