from pathlib import Path
import shutil
import argparse
import os

from src.dataset.steps.utils import get_rocq_files
from src.parser.segments import str_to_comment_list

"""
Step 0: remove comments, remove all non source file.
"""

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
    parser.add_argument("--input", type=str, default="export/mathcomp", help="Path of the dataset")
    parser.add_argument("--output", type=str, default="export/output/steps/step_0", help="Path of the output of this step")
    args = parser.parse_args()
    output_dir = Path(args.output, Path(args.input).stem)
    os.makedirs(output_dir, exist_ok=True)
    shutil.copytree(args.input, output_dir, dirs_exist_ok=True)
    make(output_dir)

