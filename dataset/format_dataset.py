import os
import re
from pathlib import Path
from tqdm import tqdm
import json

def get_rocq_files(directory):
    """Retrieve all Rocq files in a directory."""
    files = []
    for path in directory.iterdir():
        if path.is_file():
            if path.suffix == ".v":
                files.append(path)
        elif path.is_dir():
            files += get_rocq_files(path)

    return files

def remove_comments_in_file(path):
    """Remove Rocq comments in a file."""
    with open(path, "r") as file:
        content = file.read()

    pattern = re.compile(r"(\(\*[\s\S]*?\*\))")
    comments = pattern.finditer(content)

    for comment in comments:
        content = content.replace(comment.group(1), "")

    new_path = path.parent.joinpath(path.stem + "_uncommented.v")
    with open(new_path, "w") as file:
        file.write(content)

    return new_path

def get_theorems_in_file(path):
    """Find all theorems in a file."""
    with open(path, "r") as file:
        content = file.read()

    pattern = re.compile(r"(?<!\S)(?P<theorem>(Theorem|Lemma|Fact|Remark|Corollary|Proposition|Property)\s[\s\S]*?(Defined|Qed).)")
    theorems = pattern.finditer(content)
    path = str(path).replace("_uncommented", "")
    theorems = [(path, match.group("theorem")) for match in theorems]

    return theorems

def format_theorem(thm):
    """Retrieve the statement and the proof of a theorem."""
    match = re.match(r"(?P<statement>(Theorem|Lemma|Fact|Remark|Corollary|Proposition|Property)\s*(?P<name>[_a-zA-Z0-9]*)[\s\S]*?\.)\s+(?P<proof>[\s\S]*(Defined|Qed)\.)", thm)

    statement = match.group("statement")
    name = match.group("name")
    proof = match.group("proof")
    return name, statement, proof

rocq_keywords = [
    "Lemma",
    "Theorem",
    "Fact",
    "Remark",
    "Corollary",
    "Proposition",
    "Property",
    "Proof",
    "Defined",
    "Qed",
    "have",
    "move",
    "intro",
    "intros",
    "induction",
    "rewrite",
    "by",
    "at",
    "apply"
]

def find_dependencies(name, code, valid_names):
    pattern = re.compile(r"(?P<name>[_a-zA-Z0-9]*)")
    all_names = [match.group("name") for match in pattern.finditer(code)]
    all_names_except_thm_name = [n for n in all_names if n != name]
    all_names_except_thm_name_keywords = [n for n in all_names_except_thm_name if not n in rocq_keywords]
    all_valid_names = [n for n in all_names_except_thm_name_keywords if n in valid_names]
    return all_valid_names

def find_theorem_dependencies(thm, names):
    name, thm = thm
    statement, proof = thm["statement"], thm["proof"]
    statement_deps = find_dependencies(name, statement, names)
    proof_deps = find_dependencies(name, proof, names)
    return name, thm | {"statement_deps": statement_deps, "proof_deps": proof_deps}

def make(dataset):
    """
    Format the dataset.
    """

    datafile = Path(f"{dataset}.jsonl")

    if datafile.exists():
        print("Formatted dataset already here.")
    else:

        print("Making the formatted dataset.")

        print("  Get all Rocq files ...")
        directory = Path(dataset)
        files = get_rocq_files(directory)

        print("  Remove comments from files ...")
        uncommented_files = list(map(remove_comments_in_file, files))

        print("  Find theorems in files ...")
        theorems = []
        for theorems_in_file in map(get_theorems_in_file, uncommented_files):
            theorems += theorems_in_file

        print("  Total number of theorems:", len(theorems))

        for uncommented_file in uncommented_files:
            os.remove(uncommented_file)

        print("  Formatting theorems ...")
        theorems = [(f, format_theorem(thm)) for f, thm in theorems]
        theorems = [{"name": n, "filepath": f, "statement": s, "proof": p} for f, (n, s, p) in theorems]

        print("  Save the dataset ...")
        with open(datafile, "w") as f:
            for theorem in theorems:
                theorem = json.dumps(theorem)
                f.write(theorem + '\n')

        print("  DONE!")

if __name__ == "__main__":
    make("math-comp")
