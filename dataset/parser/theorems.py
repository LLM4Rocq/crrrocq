import re
from typing import Tuple
from pathlib import Path

# ====================
# Utils
# ====================

def add_to_module_list(ml, s):
    """Add the string `s` to a module list."""
    if len(s) > 0:
        if isinstance(ml[-1], str):
            ml[-1] += s
        else:
            ml.append(s)

# ====================
# Theorems
# ====================

def remove_comments(content: str) -> str:
    """Remove Rocq comments in a file."""

    match = re.search(r"\(\*[\s\S]*?\*\)", content)
    while match:
        content = content[:match.start()] + content[match.end():]
        match = re.search(r"\(\*[\s\S]*?\*\)", content)

    return content

def read_modules(content: str) -> list:
    """Split some content module by module."""

    result = [("", [""])]

    open_match = re.search(r"\sModule\s(?P<name>[_'a-zA-Z0-9]*)\.\s", content)
    while open_match:
        module_name = open_match.group("name")
        add_to_module_list(result[-1][1], content[:open_match.start()+1])
        result.append((module_name, [content[open_match.start()+1:open_match.end()]]))
        content = content[open_match.end():]

        open_match = re.search(r"\sModule\s(?P<name>[_'a-zA-Z0-9]*)\.\s", content)
        close_module = f"End {module_name}."
        close_idx = content.find(close_module)
        if close_idx < 0:
            raise Exception(f"Error: the module {module_name} is not closed.")

        while close_idx >= 0:

            if not open_match or (close_idx < open_match.start()):
                add_to_module_list(result[-1][1], content[:close_idx+len(close_module)])
                module = result.pop()
                result[-1][1].append(module)
                content = content[close_idx+len(close_module):]

                open_match = re.search(r"\sModule\s(?P<name>[_'a-zA-Z0-9]*)\.\s", content)
                if len(result) == 1:
                    close_idx = -1
                else:
                    module_name = result[-1][0]
                    close_module = f"End {module_name}."
                    close_idx = content.find(close_module)
                    if close_idx < 0:
                        raise Exception(f"Error: the module {module_name} is not closed.")
            else:
                break

    add_to_module_list(result[-1][1], content)

    if len(result) != 1:
        raise Exception("Error: wrong parsing of modules.")
    return result[0][1]

def read_theorems_in_content(content: str) -> list:
    """Find all theorems in some content."""

    pattern = re.compile(r"(?<!\S)(?P<theorem>(Theorem|Lemma|Fact|Remark|Corollary|Proposition|Property)\s[\s\S]*?(Defined|Qed).)")
    matches = pattern.finditer(content)
    theorems = [match.group("theorem") for match in matches]

    return theorems

def read_theorems_in_module_list(prefix: str, module_list: list) -> list[Tuple[str, str]]:
    """Find all theorems in a module list and compute the right prefix."""

    all_theorems = []
    for section in module_list:
        if isinstance(section, str):
            theorems = read_theorems_in_content(section)
            all_theorems += [(prefix, theorem) for theorem in theorems]
        else:
            all_theorems += read_theorems_in_module_list(prefix + '.' + section[0], section[1])

    return all_theorems

def path_to_prefix(path: Path) -> str:
    parent = path.parent
    parent = str(parent).replace('/', '.')
    if len(parent) > 0:
        return parent + '.' + path.stem
    else:
        return path.stem

def read_theorems_in_file(path: Path) -> list[Tuple[str, str]]:
    """Find all theorems in a file and compute the right prefix."""

    with open(path, "r") as f:
        content = f.read()

    prefix = path_to_prefix(path)
    content = remove_comments(content)
    module_list = read_modules(content)

    return read_theorems_in_module_list(prefix, module_list)

def format_theorem(prefix: str, theorem: str) -> Tuple[str, dict[str, str]]:
    """Retrieve the statement and the proof of a theorem."""

    match = re.match(r"(?P<statement>(Theorem|Lemma|Fact|Remark|Corollary|Proposition|Property)\s*(?P<name>[_a-zA-Z0-9']*)[\s\S]*?\.)\s+(?P<proof>[\s\S]*(Defined|Qed)\.)", theorem)
    qualid_name = prefix + '.' + match.group("name")
    return qualid_name, {"statement": match.group("statement"), "proof": match.group("proof")}
