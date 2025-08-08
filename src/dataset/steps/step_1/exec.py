import json
import os
import argparse
from pathlib import Path

from tqdm import tqdm

from src.dataset.steps.step_0.exec import get_rocq_files
from src.parser.theorems import read_theorems_in_file, format_theorem

"""
Step 1: extract all theorems from a dataset.
"""

def trim_prefix(parent_dir: Path, prefix: str) -> str:
    """Remove the part corresponding to the parent directory in a prefix."""
    parent_dir = (str(parent_dir) + '/').replace('/', '.')
    return prefix.replace(parent_dir, "")

def trim_filepath(parent_dir: Path, filepath: Path) -> str:
    """Remove the part corresponding to the parent directory in a filepath."""
    return str(filepath).replace(str(parent_dir) + '/', "")

def make(dataset, export_dir):
    """
    Read the dataset.
    """

    dataset = Path(dataset)

    files = get_rocq_files(dataset)

    theorems = []
    for file in tqdm(files):
        file_theorems = read_theorems_in_file(file)
        theorems += [(file, trim_prefix(dataset.parent, prefix), theorem) for prefix, theorem in file_theorems]

    theorems = [(str(dataset.parent), trim_filepath(dataset.parent, file), format_theorem(prefix, theorem, file)) for file, prefix, theorem in tqdm(theorems)]
    theorems = {qualid_name: {"filepath_prefix": pfile, "filepath": file} | theorem for pfile, file, (qualid_name, theorem) in theorems}

    print("  Total number of theorems:", len(list(theorems)))

    with open(Path(export_dir, f"{dataset.stem}.json"), "w") as f:
        json.dump(theorems, f, indent=4)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retrieve all Rocq theorems from a dataset and extract some information about them.")
    parser.add_argument("--input", type=str, default="export/output/steps/step_0/mathcomp", help="Path of the output of the previous step")
    parser.add_argument("--output", type=str, default="export/output/steps/step_1/", help="Path of the output of this step")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    make(args.input, args.output)
