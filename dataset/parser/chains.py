from dataclasses import dataclass

from .segments import Segment, Parentheses, Braces, Brackets, LtLtGtGt, str_to_segment_list

# =============================== Raw-chain-lists ================================
#
# With a proof as a string as input, we want to retrieve a list of Rocq chains,
# sequences of tactics linked by semicolons and separated by points. We call such
# list a raw-chain-list.
#
# For example, the proof
#
#       Proof.
#       by apply: (iffP (unitrP x)) => [[y []] | [y]]; exists y; rewrite // mulrC.
#       Qed.
#
# is translated to the raw-chain-list
#
#       [
#         'Proof.',
#         '\nby apply: (iffP (unitrP x)) => [[y []] | [y]]; exists y; rewrite // mulrC.',
#         '\nQed.'
#       ]
#
# ================================================================================

def find_point(text):
    """Find the first point followed by a blank space (or nothing if it is the last character) in a text."""

    p = text.find('.')
    res = p
    while 0 <= res < len(text):
        if len(text) == 1 or (res == 0 and text[1].isspace()) or (res == len(text) - 1 and text[-2] != '.') or (0 < res < len(text) - 1 and text[res-1] != '.' and text[res+1].isspace()):
            return res

        text_end = text[res+1:] if len(text) > res + 1 else ""
        p = text_end.find('.')
        res = res + 1 + p if p >= 0 else -1

    return -1

def proof_to_raw_chain_list(proof: str) -> list[str]:
    """Decompose a proof as a raw-chain-list."""

    raw_chain_list = []

    p = find_point(proof)
    while p >= 0:
        raw_chain_list.append(proof[:p+1])
        proof = proof[p+1:] if len(proof) > p + 1 else ""
        p = find_point(proof)

    if len(proof) > 0:
        raw_chain_list.append(proof)
    return raw_chain_list

def raw_chain_list_to_str(raw_chain_list: list[str]) -> str:
    return "".join(raw_chain_list)

# ==================================== Chain =====================================
#
# Now, we want to decompose each raw-chain from a raw-chain-list into a chain of
# Rocq tactics linked by semicolons.
#
# For example, the raw-chain
#
#       [
#         'Proof.',
#         '\nby apply: (iffP (unitrP x)) => [[y []] | [y]]; exists y; rewrite // mulrC.',
#         '\nQed.'
#       ]
#
# is translated to
#
#       [
#         Chain(tactics=[Tactic(tactic='Proof')], suffix='.'),
#         Chain(tactics=[
#           By(prefix='\n', chain=Chain(tactics=[
#             Tactic(tactic=' apply: (iffP (unitrP x)) => [[y []] | [y]]'),
#             Tactic(tactic=' exists y'),
#             Tactic(tactic=' rewrite // mulrC')
#           ], suffix=''))
#         ], suffix='.'),
#         Chain(tactics=[Tactic(tactic='\nQed')], suffix='.')
#       ]
#
# ================================================================================

@dataclass
class Chain():
    tactics: list
    suffix: str

    def __str__(self):
        return ";".join(map(str, self.tactics)) + self.suffix

@dataclass
class Tactic():
    tactic: str

    def __str__(self):
        return self.tactic

@dataclass
class BranchTactic():
    prefix: str
    chains: list[Chain]
    suffix: str

    def __str__(self):
        return self.prefix + "[" + "|".join(map(str, self.chains)) + "]" + self.suffix

def isblank(s: str):
    """Check if a string is only made of blank character."""
    return len(s) == 0 or s.isspace()

def split_branching(segment_list: list[Segment]) -> list[str]:
    """Split a segment-list in case of a branching data structure."""
    raw_chains = [""]
    for segment in segment_list:
        # We look for the split character "|" only in strings
        if isinstance(segment, str):
            s = segment.find("|")
            while s >= 0:
                raw_chains[-1] += segment[:s]
                raw_chains.append("")
                segment = segment[s+1:] if len(segment) > s + 1 else ""
                s = segment.find("|")
            raw_chains[-1] += segment

        elif isinstance(segment, Parentheses) or isinstance(segment, Braces) or isinstance(segment, Brackets) or isinstance(segment, LtLtGtGt):
            raw_chains[-1] += str(segment)

    return raw_chains

def raw_chain_to_chain(raw_chain: str) -> Chain:
    """Decompose a raw-chain into a chain."""

    if len(raw_chain) > 0 and raw_chain[-1] == '.':
        suffix = '.'
        raw_chain = raw_chain[:-1]
    else:
        suffix = ''

    tactics = []
    previous = ""
    segment_raw_chain = str_to_segment_list(raw_chain)
    for i, segment in enumerate(segment_raw_chain):

        # If the segment is a string, it is read to find tactics
        if isinstance(segment, str):

            # Read the tactics (before the by if there is one)
            s = segment.find(";")
            segment = previous + segment
            s = len(previous) + s if s >= 0 else -1

            while s >= 0:
                if s > 0:
                    tactics.append(Tactic(segment[:s]))
                segment = segment[s+1:] if len(segment) > s + 1 else ""
                s = segment.find(";")

            previous = segment

        # If the segment is a brackets and the previous variable is blank, it means we have a branching tactic
        elif isinstance(segment, Brackets) and isblank(previous) and len(str(segment)) > 2:
            # Remove the first and last characters of segment
            segment.segment_list[0] = segment.segment_list[0][1:]
            segment.segment_list[-1] = segment.segment_list[-1][:-1]

            branch_raw_chains = split_branching(segment.segment_list)
            branch_chains = list(map(raw_chain_to_chain, branch_raw_chains))

            # Get the suffix of the branch
            if len(segment_raw_chain) == i + 1:
                branch_suffix = ""
            else:
                next_segment = segment_raw_chain[i+1]
                s = next_segment.find(";")
                branch_suffix = next_segment[:s] if s >= 0 else next_segment
                segment_raw_chain[i+1] = next_segment[s+1:] if s >= 0 and len(next_segment) > s + 1 else ""

            tactics.append(BranchTactic(previous, branch_chains, branch_suffix))
            previous = ""

        # If the segment is a bracket following some non-blank text, or if the segment is a parentheses, a braces or a ltltgtgt, it is simply added to the previous tactic
        elif isinstance(segment, Brackets) or isinstance(segment, Parentheses) or isinstance(segment, Braces) or isinstance(segment, LtLtGtGt):
            previous += str(segment)

    # What is remaining is considered a final tactic
    if len(previous) > 0:
        tactics.append(Tactic(previous))

    return Chain(tactics, suffix)

def raw_chain_list_to_chain_list(raw_chain_list: list[str]) -> list[Chain]:
    return list(map(raw_chain_to_chain, raw_chain_list))

def proof_to_chain_list(proof: str) -> list[Chain]:
    return raw_chain_list_to_chain_list(proof_to_raw_chain_list(proof))

def chain_list_to_str(chain_list: list[Chain]) -> str:
    return "".join(map(str, chain_list))

def copy_str(s: str) -> str:
    return (s + ' ')[:-1]

def copy_chain(chain: Chain) -> Chain:
    new_tactics = []
    for tactic in chain.tactics:
        if isinstance(tactic, Tactic):
            new_tactics.append(Tactic(copy_str(tactic.tactic)))
        elif isinstance(tactic, BranchTactic):
            new_branch_chain = list(map(copy_chain, tactic.chains))
            new_tactics.append(BranchTactic(copy_str(tactic.prefix), new_branch_chain, copy_str(tactic.suffix)))
    return Chain(new_tactics, copy_str(chain.suffix))

def copy_chain_list(chain_list: list[Chain]) -> list[Chain]:
    return list(map(copy_chain, chain_list))

def number_of_tactics_chain(chain: Chain) -> Chain:
    res = 0
    for tactic in chain.tactics:
        if isinstance(tactic, Tactic):
            res += 1
        elif isinstance(tactic, BranchTactic):
            res += sum(map(number_of_tactics_chain, tactic.chains))
    return res

# ====================
# Testing
# ====================

import json
from tqdm import tqdm

if __name__ == "__main__":

    theorems = []
    with open("math-comp.jsonl", "r") as f:
        for line in f:
            theorems.append(json.loads(line))

    for theorem in tqdm(theorems):
        proof = theorem["proof"]

        raw_chain_list = proof_to_raw_chain_list(proof)
        reproof = raw_chain_list_to_str(raw_chain_list)
        assert (proof == reproof)

        chain_list = proof_to_chain_list(proof)
        reproof = chain_list_to_str(chain_list)
        assert (proof == reproof)
