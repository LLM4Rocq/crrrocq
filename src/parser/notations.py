import re
from typing import Any, Tuple
from pathlib import Path

from pytanque import Pytanque, State, Goal, PetanqueError

from src.parser.goals import pp_hypothesis

def find_notations(pet: Pytanque, state: State, ty: str, bad: list) -> list:
    """Find notations in some Rocq type."""
    try:
        pre_notations = pet.list_notations_in_statement(state, "Lemma find_notations_in_some_type : " + ty + ".")
        [notation.pop("locations") for notation in pre_notations]

        notations = []
        for notation in pre_notations:
            if not notation in bad + notations:
                notations.append(notation)

        return notations
    except PetanqueError:
        return []

def list_to_dict(nota_list: list) -> dict:
    """Transform a list of notations into a dictionary of notations."""

    nota_dict = {"scope": {}, "noscope": {}}
    for cnot in nota_list:
        qualid_name = cnot["path"] + ('.' + cnot["secpath"] if cnot["secpath"] != "<>" else "") + '.' + cnot["notation"]
        if cnot["scope"]:
            if not cnot["scope"] in nota_dict["scope"]:
                nota_dict["scope"][cnot["scope"]] = {}
            d = nota_dict["scope"][cnot["scope"]]
        else:
            d = nota_dict["noscope"]

        d[qualid_name] = {"name": cnot["notation"]}

    return nota_dict

def dict_to_list(nota_dict: dict) -> list:
    """Transform a dictionary of notations into a list of notations."""
    nota_list = []

    for _, scope_content in nota_dict["scope"].items():
        for notation, notation_content in scope_content.items():
            notation_content["fullname"] = notation
            nota_list.append(notation_content)

    for notation, notation_content in nota_dict["noscope"].items():
        notation_content["fullname"] = notation
        nota_list.append(notation_content)

    return nota_list

def format_notations(pet: Pytanque, state: State, notations_list: list, filepath: str, dictionary: dict) -> list:
    """Format notations."""

    filepath = Path(filepath)
    filename = filepath.stem

    notations_dict = list_to_dict(notations_list)
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

    return dict_to_list(new_notations_dict)

def notations_in_goal(pet: Pytanque, state: State, goal: Goal, raw_goal: Goal, bad: list, filepath: str, dictionary: dict, statement=None) -> list:
    """Find and format all notations appearing in a goal."""

    # Variable state to keep track of hypotheses already defined
    var_state = state

    notations = []
    for hyp, raw_hyp in zip(goal.hyps, raw_goal.hyps):

        # Notations in the definition
        if hyp.def_:
            notations += find_notations(pet, var_state, hyp.def_, notations + bad)

        # Notations in the type
        notations += find_notations(pet, var_state, hyp.ty, notations + bad)

        # Update the variable state
        raw_hyp_str = pp_hypothesis(raw_hyp.names, None, raw_hyp.ty)
        var_state = pet.run(var_state, f"Parameters {raw_hyp_str}.")

    statement_str = statement if statement else goal.ty
    notations += find_notations(pet, var_state, statement_str, notations + bad)

    return format_notations(pet, state, notations, filepath, dictionary)

def notation_to_str(notation: dict) -> str:
    """Return a string version of a notation."""

    print("=============================")
    print(notation)
    print("=============================")

    if "info" in notation:
        str_not = notation["info"]["fullname"]
        if "docstring" in notation["info"]:
            str_not += "\n" + notation["info"]["docstring"]

    else:
        str_not = notation["name"]

    return str_not

def notations_to_str(notations: list) -> str:
    """Return a string version of a notations list."""
    return "\n\n".join(map(notation_to_str, notations))
