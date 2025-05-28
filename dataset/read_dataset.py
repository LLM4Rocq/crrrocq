import json
import argparse
from pathlib import Path
from tqdm import tqdm

from trim_dataset import get_rocq_files
from parser.theorems import read_theorems_in_file, format_theorem

def make(dataset):
    """
    Read the dataset.
    """

    dataset = Path(dataset)
    savefile = Path(dataset.stem + ".json")

    if savefile.exists():
        print("Read dataset already here.")
    else:

        print("Making the read dataset.")

        print("  Get all Rocq files ...")
        files = get_rocq_files(dataset)

        print("  Read theorems in files ...")
        theorems = []
        for file in files:
            file_theorems = read_theorems_in_file(file)
            theorems += [(file, prefix, theorem) for prefix, theorem in file_theorems]

        print("  Total number of theorems:", len(theorems))

        print("  Extracting the statements and proofs of theorems ...")
        theorems = [(str(file), format_theorem(prefix, theorem, file)) for file, prefix, theorem in tqdm(theorems)]
        theorems = {qualid_name: {"filepath": file} | theorem for file, (qualid_name, theorem) in theorems}

        print("  Save the dataset ...")
        with open(savefile, "w") as f:
            json.dump(theorems, f, indent=2)

        print("  DONE!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retrieve all Rocq theorems from a dataset and extract some information about them.")
    parser.add_argument("--dataset", type=str, default="mathcomp", help="The path of the dataset, default is 'mathcomp'")
    args = parser.parse_args()
    make(args.dataset)
