import re
from typing import Any, Optional, Tuple
from pathlib import Path

from pytanque import Pytanque, State, Goal, PetanqueError

from src.parser.goals import pp_hypothesis

def remove_duplicates(l: list) -> list:
    """Remove duplicates from a list."""
    new_l = []
    for e in l:
        if not e in new_l:
            new_l.append(e)
    return new_l

def find_notations(pet: Pytanque, state: State, ty: str) -> list:
    """Find notations in some Rocq type."""
    try:
        notations = pet.list_notations_in_statement(state, "Lemma find_notations_in_some_type : " + ty + ".")
        [notation.pop("locations") for notation in notations]
        return remove_duplicates(notations)
    except PetanqueError:
        return []

def format_notation(pet: Pytanque, state: State, notation: dict, filepath: str, scopes: list, dictionary: dict) -> Optional[list]:
    """Format a notation."""

    filepath = Path(filepath)
    filename = filepath.stem

    # Compute the qualified name of the notation
    qname = notation["path"] + ('.' + notation["secpath"] if notation["secpath"] != "<>" else "") + '.' + notation["notation"]
    if filename == qname.split('.', maxsplit=1)[0]:
        qname = '.'.join(list(filepath.parent.parts) + [qname])

    # Locate similar notations
    lstate = pet.run(state, f'Locate "{notation["notation"]}".')
    message = lstate.feedback[0][1]

    if message == "Unknown notation":
        return None

    # Extract all notations found
    notations = []
    for match in re.finditer(r'Notation\s(?P<notation>"[\s\S]+?")\s:=[\s\S]*?(\s(?=Notation)|\Z)', message):
        notations.append((match.group("notation"), match.group(0)))

    # Find the right notation
    name, body = None, None

    if notation["scope"]:
        for n, b in notations:
            if (" : " + notation["scope"]) in b:
                name, body = n, b
                break

    else:
        for n, b in notations:
            if (not (" : " + scope) in b for scope in scopes):
                name, body = n, b
                break

    if not name or not body:
        raise Exception("Error: there should be a notation matched.")

    # Format the notation
    qname = qname.replace(notation["notation"], name)
    notation.pop("path")
    notation.pop("secpath")
    notation["qname"] = qname
    notation["locate"] = body.replace("(default interpretation)", "").strip()

    if notation["scope"]:
        if notation["scope"] in dictionary["scope"]:
            d = dictionary["scope"][notation["scope"]]
        else:
            d = None
    else:
        d = dictionary["noscope"]

    if d and qname in d:
        notation["info"] = d[qname]

    return notation

def format_notations(pet: Pytanque, state: State, notations: list, filepath: str, scopes: list, dictionary: dict) -> list:
    """Format notations."""
    notations = [format_notation(pet, state, notation, filepath, scopes, dictionary) for notation in notations]
    return [notation for notation in notations if notation]

def notations_in_goal(pet: Pytanque, state: State, goal: Goal, raw_goal: Goal, global_variables: list, filepath: str, scopes: list, dictionary: dict, statement=None) -> list:
    """Find and format all notations appearing in a goal."""

    # Variable state to keep track of hypotheses already defined
    var_state = state

    notations = []
    for hyp, raw_hyp in zip(goal.hyps, raw_goal.hyps):

        # Notations in the definition
        if hyp.def_:
            notations += find_notations(pet, var_state, hyp.def_)

        # Notations in the type
        notations += find_notations(pet, var_state, hyp.ty)

        # Update the variable state
        names_wo_gvars = [name for name in raw_hyp.names if not name in global_variables]
        if len(names_wo_gvars) > 0:
            if raw_hyp.def_:
                for name in names_wo_gvars:
                    var_state = pet.run(var_state, "Unset Implicit Arguments. Definition " + name + " := " + raw_hyp.def_ + " : " + raw_hyp.ty + ". Set Implicit Arguments.")
            else:
                var_state = pet.run(var_state, "Unset Implicit Arguments. Parameters " + " ".join(names_wo_gvars) + " : " + raw_hyp.ty + ". Set Implicit Arguments.")

    statement_str = statement if statement else goal.ty
    notations += find_notations(pet, var_state, statement_str)

    notations = remove_duplicates(notations)
    return format_notations(pet, state, notations, filepath, scopes, dictionary)

def notation_to_str(notation: dict) -> str:
    """Return a string version of a notation."""

    if "info" in notation:
        str_not = notation["info"]["fullname"]
        if "docstring" in notation["info"]:
            str_not += "\n" + notation["info"]["docstring"]

    else:
        str_not = notation["locate"]

    return str_not

def notations_to_str(notations: list) -> str:
    """Return a string version of a notations list."""
    return "\n\n".join(map(notation_to_str, notations))
