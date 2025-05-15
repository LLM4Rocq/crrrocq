from typing import Optional
from dataclasses import dataclass
from abc import ABC, abstractmethod

# ================================ Segment-lists =================================
#
# With a proof given as a string, we want to extract the parts that are inside
# Rocq's logic segments.
#
# We refer to logic segments as just segments, they can be delimited by
# parentheses, braces, brackets or <<...>>.
#
# Our output will be a list alternating between the parts of our input string
# inside and outside of segments.
# Let's call such lists 'segment-lists'.
#
# In a segment-list, the parts outside segments are simply strings.
# The parts inside a segment are stored as segment-list to take into account the
# nesting of segments.
#
# For example, the string
#
#       Proof.
#       by apply: (iffP (unitrP x)) => [[y []] | [y]]; exists y; rewrite // mulrC.
#       Qed.
#
# is translated to the segment-list
#
#       [
#         'Proof.\nby apply: ',
#         Parentheses(segment_list=[
#           '(iffP ',
#           Parentheses(segment_list=['(unitrP x)']),
#           ')'
#         ]),
#         ' => ',
#         Brackets(segment_list=[
#           '[',
#           Brackets(segment_list=[
#             '[y ',
#             Brackets(segment_list=['[]']),
#             ']'
#           ]),
#           ' | ',
#           Brackets(segment_list=['[y]']),
#           ']'
#         ]),
#         '; exists y; rewrite // mulrC.\nQed.'
#       ]
#
# ================================================================================

# ====================
# Utils
# ====================

def pop_from_segment_list(sl) -> Optional[str]:
    """Pop one character from a segment-list."""
    if len(sl) == 0:
        return None
    else:
        if isinstance(sl[-1], str):
            if len(sl[-1]) > 1:
                res, sl[-1] = sl[-1][-1], sl[-1][:-1]
                return res
            elif len(sl[-1]) == 1:
                return sl.pop()
            else:
                sl.pop()
                return pop_from_segment_list(sl)
        else:
            res = pop_from_segment_list(sl[-1].segment_list)
            if len(sl[-1].segment_list) == 0:
                sl.pop()
            if res:
                return res
            else:
                return pop_from_segment_list(sl)

def remove_from_segment_list(sl, n):
    """Remove `n` characters from a segment-list."""
    for _ in range(n):
        pop_from_segment_list(sl)

def add_to_segment_list(sl, c):
    """Add the string `c` to a segment-list."""
    if len(c) > 0:
        if isinstance(sl[-1], str):
            sl[-1] += c
        else:
            sl.append(c)

# ====================
# Segments
# ====================

@dataclass
class Segment(ABC):
    segment_list: list

    def __str__(self):
        return "".join(map(str, self.segment_list))

class SegmentReader(ABC):
    def __init__(self):
        self.open = False
        self.nbr_open = 0
        self.close = False
        self.previous = ""
        self.remove = 0

    @abstractmethod
    def make_segment(self, segment_list: list) -> Segment:
        pass

    @abstractmethod
    def check_open(self, c: str) -> Optional[str]:
        pass

    @abstractmethod
    def check_close(self, c: str) -> Optional[str]:
        pass

    def default_update(self, c: str):
        pass

    def update(self, c: str) -> str:
        self.open = False
        new_c_open = self.check_open(c)
        self.close = False
        new_c_close = self.check_close(c)

        if new_c_open != None:
            self.open = True
            self.nbr_open += 1
            return new_c_open
        elif self.nbr_open > 0 and new_c_close != None:
            self.close = True
            self.nbr_open -= 1
            return new_c_close
        else:
            self.default_update(c)
            return c

# ====================
# Parentheses
# ====================

class Parentheses(Segment):
    pass

class ParenthesesReader(SegmentReader):
    def make_segment(self, segment_list):
        return Parentheses(segment_list)

    def check_open(self, c):
        return c if c == '(' else None

    def check_close(self, c):
        return c if c == ')' else None

# ====================
# Braces
# ====================

class Braces(Segment):
    pass

class BracesReader(SegmentReader):
    def make_segment(self, segment_list):
        return Braces(segment_list)

    def check_open(self, c):
        return c if c == '{' else None

    def check_close(self, c):
        return c if c == '}' else None

# ====================
# Brackets
# ====================

class Brackets(Segment):
    pass

class BracketsReader(SegmentReader):
    def __init__(self):
        super().__init__()
        self.interval = False
        self.backtic = False

    def make_segment(self, segment_list):
        return Brackets(segment_list)

    def check_open(self, c):
        if self.backtic or self.interval:
            return None
        else:
            return c if c == '[' else None

    def check_close(self, c):
        if self.interval:
            return None
        else:
            return c if c == ']' else None

    def default_update(self, c):
        if self.backtic:
            if c == '[' or c == ']':
                self.interval = True
            else:
                self.backtic = False
        elif not self.interval and c == '`':
            self.backtic = True
        elif self.interval and (c == '[' or c == ']'):
            self.interval = False

# ====================
# LtLtGtGt
# ====================

class LtLtGtGt(Segment):
    pass

class LtLtGtGtReader(SegmentReader):
    def make_segment(self, segment_list):
        return LtLtGtGt(segment_list)

    def check_open(self, c):
        if self.previous == '<':
            self.previous = ""
            self.remove = 1
            return '<' + c if c == '<' else None
        else:
            return None

    def check_close(self, c):
        if self.previous == '>':
            self.previous = ""
            return c if c == '>' else None
        else:
            return None

    def default_update(self, c):
        if c == '<':
            self.previous = '<'
        elif c == '>':
            self.previous = '>'
        else:
            self.previous = ""

# ====================
# Main
# ====================

segment_readers = [
    ParenthesesReader(),
    BracesReader(),
    BracketsReader(),
    LtLtGtGtReader()
]

def str_to_segment_list(string: str) -> list[Segment]:
    """Decompose a string into a segment-list."""
    segment_list_list = [[""]]

    opened = []
    for c in string:
        new_cs = [reader.update(c) for reader in segment_readers]

        reader = None
        for i, r in enumerate(segment_readers):
            if r.open or r.close:
                reader = r
                break

        if reader:

            if reader.open:
                opened.append(type(reader))
                remove_from_segment_list(segment_list_list[-1], reader.remove)
                segment_list_list.append([new_cs[i]])

            elif reader.close:
                if len(opened) == 0:
                    raise Exception("Error: too many closing segments.")

                if type(reader) != opened[-1]:
                    raise Exception(f"Error: a {type(reader)} is trying to close a {opened[-1]}")
                opened.pop()

                segment_list = segment_list_list.pop()
                add_to_segment_list(segment_list, new_cs[i])
                segment_list_list[-1].append(reader.make_segment(segment_list))

            reader.remove = 0

        else:
            add_to_segment_list(segment_list_list[-1], c)

    if len(segment_list_list) > 1:
        raise Exception("Error: too many opening segments.")
    return segment_list_list[0]

def segment_list_to_str(segment_list: list[Segment]) -> str:
    return "".join(map(str, segment_list))

# ====================
# Testing
# ====================

import json
from tqdm import tqdm

if __name__ == "__main__":

    theorems = []
    with open("../dataset/math-comp.jsonl", "r") as f:
        for line in f:
            theorems.append(json.loads(line))

    for theorem in tqdm(theorems):
        proof = theorem["proof"]
        segment_list = str_to_segment_list(proof)
        reproof = segment_list_to_str(segment_list)
        assert (proof == reproof)
