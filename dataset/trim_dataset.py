import re
from pathlib import Path
import argparse

from parser.segments import str_to_comment_list

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

def remove_comments(content: str) -> str:
    """Remove Rocq comments in a file."""

    comment_list = str_to_comment_list(content)

    content = ""
    for segment in comment_list:
        if isinstance(segment, str):
            content += segment

    return content

def make(dataset: str):
    """
    Trim the dataset.
    """

    dataset = Path(dataset)

    print("Triming the dataset.")

    print("  Get all Rocq files ...")
    files = get_rocq_files(dataset)

    print("  Remove comments in Rocq files ...")
    for file in files:
        with open(file, "r") as f:
            content = f.read()
        content = remove_comments(content)
        with open(file, "w") as f:
            f.write(content)

    print("  DONE!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Keep only Rocq and Make files, remove comments in Rocq files.")
    parser.add_argument("--dataset", type=str, default="mathcomp", help="The path of the dataset, default is 'mathcomp'")
    args = parser.parse_args()
    make(args.dataset)

