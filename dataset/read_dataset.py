import os
import re
import json
import argparse
from pathlib import Path

def get_rocq_files(directory, prefix=""):
    """Retrieve all Rocq files in a directory."""
    files = []
    for path in directory.iterdir():
        if path.is_file():
            if path.suffix == ".v":
                files.append(Path(prefix, path.name))
        elif path.is_dir():
            files += get_rocq_files(path, prefix=Path(prefix, path.stem))

    return files

def remove_comments_in_file(dataset, path):
    """Remove Rocq comments in a file."""
    with open(Path(dataset, path), "r") as file:
        content = file.read()

    pattern = re.compile(r"(\(\*[\s\S]*?\*\))")
    comments = pattern.finditer(content)

    for comment in comments:
        content = content.replace(comment.group(1), "")

    return path, content

def get_theorems_in_file(path, uncommented_file):
    """Find all theorems in a file."""
    pattern = re.compile(r"(?<!\S)(?P<theorem>(Theorem|Lemma|Fact|Remark|Corollary|Proposition|Property)\s[\s\S]*?(Defined|Qed).)")
    matches = pattern.finditer(uncommented_file)
    theorems = [match.group("theorem") for match in matches]
    pattern = re.compile(r"(Theorem|Lemma|Fact|Remark|Corollary|Proposition|Property)\s*(?P<name>[_a-zA-Z0-9']*)\s")
    matches = [(pattern.match(theorem), theorem) for theorem in theorems]
    named_theorems = {match.group("name"): theorem for match, theorem in matches}
    theorems = [(path, theorem) for theorem in named_theorems.values()]

    return theorems

def format_theorem(thm):
    """Retrieve the statement and the proof of a theorem."""
    match = re.match(r"(?P<statement>(Theorem|Lemma|Fact|Remark|Corollary|Proposition|Property)\s*(?P<name>[_a-zA-Z0-9']*)[\s\S]*?\.)\s+(?P<proof>[\s\S]*(Defined|Qed)\.)", thm)

    statement = match.group("statement")
    name = match.group("name")
    proof = match.group("proof")
    return name, statement, proof

def make(dataset):
    """
    Format the dataset.
    """

    dataset = Path(dataset)
    savefile = Path(dataset.stem + ".jsonl")

    if savefile.exists():
        print("Formatted dataset already here.")
    else:

        print("Making the formatted dataset.")

        print("  Get all Rocq files ...")
        files = get_rocq_files(dataset)

        print("  Remove comments from files ...")
        uncommented_files = [remove_comments_in_file(dataset, path) for path in files]

        print("  Find theorems in files ...")
        theorems = []
        for theorems_in_file in [get_theorems_in_file(path, file) for path, file in uncommented_files]:
            theorems += theorems_in_file

        print("  Total number of theorems:", len(theorems))

        print("  Extracting the statements and proofs of theorems ...")
        theorems = [(p, format_theorem(thm)) for p, thm in theorems]
        theorems = [{"name": n, "filepath": str(fp), "statement": s, "proof": p} for fp, (n, s, p) in theorems]

        print("  Save the dataset ...")
        with open(savefile, "w") as f:
            for theorem in theorems:
                theorem = json.dumps(theorem)
                f.write(theorem + '\n')

        print("  DONE!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retrieve all Rocq theorems from a dataset and extract their statements and proofs.")
    parser.add_argument("--dataset", type=str, default="math-comp", help="The path of the dataset, default is 'math-comp'")
    args = parser.parse_args()
    make(args.dataset)
