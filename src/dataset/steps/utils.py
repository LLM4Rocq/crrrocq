import re
import json
from typing import Tuple

from pytanque import Pytanque, State

from src.parser.theorems import end_position, add_positions

def get_rocq_files(directory):
    """Retrieve all Rocq files in a directory, and remove non-Rocq and non-Make files."""

    files = []
    for path in directory.iterdir():
        if path.is_file():
            if path.suffix == ".v":
                files.append(path)
            if path.suffix != ".v" and path.suffix != ".vo" and path.name.find("Make") < 0:
                path.unlink()
        elif path.is_dir():
            files += get_rocq_files(path)
            if not any(path.iterdir()):
                path.rmdir()

    return files

def is_proof_keyword(text: str) -> bool:
    """Return True if the text corresponds to a proof keyword: Proof, Qed or Defined."""
    return bool(re.search(r"(Proof|Qed|Defined)\.", text.strip()))


def load_dictionary(dfile: str) -> dict:
    """Load the dictionary."""

    with open(dfile, 'r') as file:
        d_base = json.load(file)

    d = {"objects": {}, "notations": d_base["notations"]}

    for object in d_base["objects"]:
        for key in object["keys"]:
            d["objects"][key] = object["value"]

    return d

def append_get_index(l: list, e) -> int:
    """Add an element to a list """
    if e in l:
        return l.index(e)
    else:
        l.append(e)
        return len(l) - 1

def get_scopes(pet: Pytanque, state: State) -> list:
    """Return the list of scopes."""

    sstate = pet.run(state, "Print Scopes.")
    message = sstate.feedback[0][1]

    scopes = []
    for match in re.finditer(r"Scope\s(?P<scope>\S*)", message):
        scopes.append(match.group("scope"))

    return scopes

def update_position(line: int, char: int, text: str) -> Tuple[int, int]:
    """Return the new line and char positions after some text is added to it."""
    l, c = end_position(text)
    return add_positions(line, char, l, c)
