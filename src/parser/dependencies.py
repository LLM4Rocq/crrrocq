import re
from typing import Any, Optional, Tuple
from pathlib import Path

from pytanque import Pytanque, State, Goal, PetanqueError

from src.parser.ast import list_dependencies

def find_dependencies(pet: Pytanque, state: State, code: str, bad: list) -> list:
    """Find dependencies in some Rocq code."""
    try:
        ast = pet.ast(state, code)
        dependencies = list_dependencies(ast)
        return [dependency for dependency in dependencies if not dependency in bad]
    except PetanqueError:
        return []

def find_dependencies_in_hypothesis(pet: Pytanque, state: State, hyp: Any, bad: list) -> list:
    """Find dependencies in some hypothesis."""
    definition = "Definition find_dependencies_in_some_hypothesis : " + hyp.ty + (" := " + hyp.def_ if hyp.def_ else "") + "."
    return find_dependencies(pet, state, definition, bad)

def find_dependencies_in_type(pet: Pytanque, state: State, ty: str, bad: list) -> list:
    """Find dependencies in some Rocq type."""
    return find_dependencies(pet, state, "Goal " + ty + ".", bad)

def format_dependency(pet: Pytanque, state: State, dependency: str, filepath: str, dictionary: dict) -> Optional[dict]:
    """Format a dependency."""

    state = pet.run(state, f"Locate Term {dependency}.")
    message = state.feedback[0][1]

    # Check if the dependency is syntactically equal to another theorem
    match = re.search(r"(Constant|Inductive|Constructor)\s*(?P<first_qualid_name>\S*)\s*\(syntactically\s*equal\s*to\s*(?P<second_qualid_name>\S*)\s*\)", message)
    if match and match.start() == 0:
        qualid_names = [match.group("first_qualid_name"), match.group("second_qualid_name")]

    else:
        # Check for normal dependency
        match = re.search(r"(Constant|Inductive|Constructor)\s*(?P<qualid_name>\S*)", message)
        if match and match.start() == 0:
            qualid_names = [match.group("qualid_name")]

        else:
            # Check for notation dependency
            match = re.search(r"Notation\s*(?P<qualid_name>\S*)", message)
            if match and match.start() == 0:
                qualid_names = [match.group("qualid_name")]

            else:
                return None

    res = {"name": dependency}

    # Get the type
    try:
        state = pet.run(state, f"About {dependency}.")
        message = state.feedback[0][1]

        match = re.search(f"{dependency}\\s*:\\s(?P<type>[\\s\\S]*?)\\n\\n", message)
        if not match:
            pass
            # TODO: Better handle notation cases
            # raise Exception(f"Error: the type of the dependency should be in {message}.")
        else:
            res["type"] = match.group("type")
    except PetanqueError:
        pass

    # Get the info
    filepath = Path(filepath)
    filename = filepath.stem
    for qname in qualid_names:

        # Check if the dependency is declared in the same file that the state is in
        if filename == qname.split('.', maxsplit=1)[0]:
            qname = '.'.join(list(filepath.parent.parts) + [qname])

        if qname in dictionary:
            res["info"] = dictionary[qname]
            break

    return res

def format_dependencies(pet: Pytanque, state: State, dependencies: list, filepath: str, dictionary: dict) -> list:
    """Format dependencies."""
    dependencies = [format_dependency(pet, state, dependency, filepath, dictionary) for dependency in dependencies]
    return [dependency for dependency in dependencies if dependency]

def dependencies_in_goal(pet: Pytanque, state: State, goal: Goal, bad: list, filepath: str, dictionary: dict, statement=None) -> Tuple[list, list]:
    """Find and format dependencies appearing in a goal."""

    dependencies = []
    for hyp in goal.hyps:
        bad += hyp.names
        new_dependencies = find_dependencies_in_hypothesis(pet, state, hyp, bad)
        bad += new_dependencies
        dependencies += new_dependencies

    statement_str = statement if statement else goal.ty
    new_dependencies = find_dependencies_in_type(pet, state, statement_str, bad)
    bad += new_dependencies
    dependencies += new_dependencies

    return format_dependencies(pet, state, dependencies, filepath, dictionary)

def dependency_to_str(dependency: dict) -> str:
    """Return a string version of a dependency."""

    if "info" in dependency:
        str_dep = dependency["info"]["fullname"].strip()
        if "docstring" in dependency["info"]:
            str_dep += "\n" + dependency["info"]["docstring"]

    else:
        str_dep = dependency["name"].strip()
        if "type" in dependency:
            str_dep += " : " + dependency["type"].strip()

    return str_dep

def dependencies_to_str(dependencies: list) -> str:
    """Return a string version of a dependencies list."""
    return "\n\n".join(map(dependency_to_str, dependencies))
