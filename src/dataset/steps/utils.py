import re

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
