import re
import json
import argparse
from pathlib import Path

from parser.theorems import read_theorems_in_file, format_theorem

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

def make(dataset):
    """
    Format the dataset.
    """

    dataset = Path(dataset)
    savefile = Path(dataset.stem + ".json")

    if savefile.exists():
        print("Formatted dataset already here.")
    else:

        print("Making the formatted dataset.")

        print("  Get all Rocq files ...")
        files = get_rocq_files(dataset)

        print("  Read theorems in files ...")
        theorems = []
        for file in files:
            file_theorems = read_theorems_in_file(file)
            theorems += [(str(file), prefix, theorem) for prefix, theorem in file_theorems]

        print("  Total number of theorems:", len(theorems))

        print("  Extracting the statements and proofs of theorems ...")
        theorems = [(file, format_theorem(prefix, theorem)) for file, prefix, theorem in theorems]
        theorems = {qualid_name: {"filepath": file} | theorem for file, (qualid_name, theorem) in theorems}

        print("  Save the dataset ...")
        with open(savefile, "w") as f:
            json.dump(theorems, f, indent=2)

        print("  DONE!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retrieve all Rocq theorems from a dataset and extract their statements and proofs.")
    parser.add_argument("--dataset", type=str, default="mathcomp", help="The path of the dataset, default is 'mathcomp'")
    args = parser.parse_args()
    make(args.dataset)
