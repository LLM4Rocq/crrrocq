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

def read_modules(content: str) -> list:
    """Split some content module by module."""

    match = re.search(r"\sModule\s(?P<name>[_'a-zA-Z0-9]*)\.\s", content)

    if match:
        result = [content[:match.start()+1]]

        module_name = match.group("name")
        close_module = f"End {module_name}."
        content = content[match.end()-1:]
        close_idx = content.find(close_module)
        if close_idx < 0:
            raise Exception(f"Error: the module {module_name} is not closed.")

        module_content = read_modules(content[:close_idx])
        module_content[0] = f"Module {module_name}." + module_content[0]
        module_content[-1] += f"End {module_name}."

        result.append((module_name, module_content))
        content = content[close_idx+len(close_module):]
        result += read_modules(content)
        return result

    else:
        return [content]

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
    module_list = read_modules(content)

    return read_theorems_in_module_list(prefix, module_list)

def get_position(content: str, index: int) -> Tuple[int, int]:
    """Return the position of some index in a string."""
    line = 0
    char = 0
    reset_char = True
    for c in content[:index+1]:
        if c == '\n':
            line += 1
            char = 0
            reset_char = True
        elif not reset_char:
            char += 1
        else:
            reset_char = False
    return line, char

def add_positions(line1, char1, line2, char2):
    """Add the first position to the second."""
    if line1 == 0:
        return line2, char1 + char2
    else:
        return line1 + line2, char1

def format_theorem(prefix: str, theorem: str, file: Path) -> Tuple[str, dict[str, str]]:
    """Retrieve the statement and the proof of a theorem."""

    match = re.match(r"(?P<statement>(Theorem|Lemma|Fact|Remark|Corollary|Proposition|Property)\s*(?P<name>[_a-zA-Z0-9']*)[\s\S]*?\.)(?P<proof>\s+[\s\S]*(Defined|Qed)\.)", theorem)
    qualid_name = prefix + '.' + match.group("name")

    with open(file, "r") as f:
        content = f.read()
    index = content.find(theorem)
    if index < 0:
        raise Exception(f"Error: the theorem {qualid_name} is not found in {str(file)}.")
    line, char = get_position(content, index)

    return qualid_name, {"position": {"line": line, "character": char}, "statement": match.group("statement"), "proof": match.group("proof")}
