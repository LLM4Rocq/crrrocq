import json
import os
import argparse
from pathlib import Path

from tqdm import tqdm

from src.dataset.steps.step_0.exec import get_rocq_files
from src.parser.theorems import read_theorems_in_file, format_theorem

"""
Step 1: extract all theorems from mathcomp.
"""
def make(dataset, export_dir):
    """
    Read the dataset.
    """

    dataset = Path(dataset)
    files = get_rocq_files(dataset)
    theorems = []
    for file in tqdm(files):
        file_theorems = read_theorems_in_file(file)
        theorems += [(file, prefix, theorem) for prefix, theorem in file_theorems]

    print("  Total number of theorems:", len(theorems))

    theorems = [(str(file), format_theorem(prefix, theorem, file)) for file, prefix, theorem in tqdm(theorems)]
    theorems = {qualid_name: {"filepath": file} | theorem for file, (qualid_name, theorem) in theorems}

    with open(os.path.join(export_dir, 'result.json'), "w") as f:
        json.dump(theorems, f, indent=4)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retrieve all Rocq theorems from a dataset and extract some information about them.")
    parser.add_argument("--input", type=str, default="export/output/steps/step_0/", help="The path of the trimmed dataset")
    parser.add_argument("--output", type=str, default="export/output/steps/step_1/", help="Output of the step 1")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    make(args.input, args.output)
