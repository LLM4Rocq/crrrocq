import re
from dataclasses import dataclass

# ================================ Bracket-lists =================================
#
# With a string as input, we want to separate the parts that are enclosed in
# parentheses, braces or brackets from those that are not.
#
# Our output will be a list alternating between the parts of our input string
# inside and outside of parentheses, braces or brackets.
# Let's call such lists 'bracket-lists'.
#
# In a bracket-list, the parts outside delimiters are simply strings.
# The parts inside delimiters are stored as bracket-list to take into account the
# nesting of delimiters.
#
# For example, the string
#       "Proof.\nby apply: (iffP (unitrP x)) => [[y []] | [y]]; exists y; rewrite // mulrC.\nQed."
#
# is equivalent to the bracket-list
#       ["Proof.\nby apply: ", ["(iffP ", ["(unitrP x)"], ")"], " => ", ["[", ["[y ", ["[]"], "]"], " | ", ["[y]"], "]"], "; exists y; rewrite // mulrC.\nQed."]
#
# ================================================================================

def add_char_to_bracket_list(bl, c):
    """Add a character to a bracket list."""
    if isinstance(bl[-1], str):
        bl[-1] += c
    elif isinstance(bl[-1], list):
        bl.append(c)

def str_to_bracket_list(string):
    """Decompose a string into a bracket-list."""
    bracket_list_list = [[""]]

    # As interval in math-comp are represented using brackets,
    # we don't want to take these brackets into accounts
    # as they might no be closed: "`[0; +oo["
    backtic = False  # Tells if the previous character is a backtic
    interval = False # Tells if we are reading an interval

    for c in string:

        # If we encounter a backtic outside of an interval, set backtic to true
        if not interval and c == '`':
            backtic = True
            add_char_to_bracket_list(bracket_list_list[-1], c)

        # If we encounter a bracket and the previous character is a backtic, set interval to True to indicate we are reading an interval
        elif backtic and (c == '[' or c == ']'):
            backtic = False
            interval = True
            add_char_to_bracket_list(bracket_list_list[-1], c)

        # If we encounter a bracket while reading an interval, set interval to False to indicate we have finished reading an interval
        elif interval and (c == '[' or c == ']'):
            interval = False
            add_char_to_bracket_list(bracket_list_list[-1], c)

        # If we encounter an opening delimiter character, we start the construction of a new bracket-list
        elif c == '[' or c == '{' or c == '(':
            backtic = False
            bracket_list_list.append([c])

        # If we encounter a closing delimiter character, we close the current bracket-list
        elif c == ']' or c == '}' or c == ')':
            backtic = False
            # If there is less than one bracket-list being constructed, it means there is no bracket to close and we return an error
            if len(bracket_list_list) <= 1:
                raise Exception("Error: too many closing brackets.")
            # Otherwise, we close the last bracket-list constructed and add it to the previous one
            else:
                bracket_list = bracket_list_list.pop()
                add_char_to_bracket_list(bracket_list, c)
                bracket_list_list[-1].append(bracket_list)

        # If we encounter a character with no special case, we add it to the last bracket-list
        else:
            backtic = False
            add_char_to_bracket_list(bracket_list_list[-1], c)

    # If there is more than one remaining bracket-list, it means some opened bracket-list have not been closed and we return an error
    if len(bracket_list_list) > 1:
        raise Exception("Error: too many opening brackets.")
    else:
        return bracket_list_list[0]

def bracket_list_to_str(bracket_list):
    """Flatten a bracket-list into a string."""

    string = ""
    for section in bracket_list:
        if isinstance(section, str):
            string += section
        elif isinstance(section, list):
            string += bracket_list_to_str(section)

    return string

def copy_bracket_list(bracket_list):
    """Return a copy of a bracket-list."""

    new_bracket_list = []
    for section in bracket_list:
        if isinstance(section, str):
            new_section = (section + ' ')[:-1] # Ugly way to copy a string
            new_bracket_list.append(new_section)
        elif isinstance(section, list):
            new_section = copy_bracket_list(section)
            new_bracket_list.append(new_section)

    return new_bracket_list

def remove_first_last_from_bracket_list(bracket_list):
    """Remove the first and last characters of a bracket-list."""

    if len(bracket_list[0]) <= 1:
        bracket_list = bracket_list[1:]
    else:
        bracket_list[0] = bracket_list[0][1:]

    if len(bracket_list[-1]) <= 1:
        bracket_list = bracket_list[:-1]
    else:
        bracket_list[-1] = bracket_list[-1][:-1]

    return bracket_list

def split_bracket_list(bracket_list, sep="|"):
    """Split a bracket-list using a separator."""
    bracket_list = remove_first_last_from_bracket_list(bracket_list)

    bracket_list_list = []
    current_bracket_list = []
    for section in bracket_list:

        if isinstance(section, str):
            b = section.find(sep)
            while b >= 0:
                before = section[:b]
                section = section[b+1:] if len(section) > b+1 else ""
                current_bracket_list.append(before)
                bracket_list_list.append(current_bracket_list)
                current_bracket_list = []
                b = section.find(sep)
            current_bracket_list.append(section)

        if isinstance(section, list):
            current_bracket_list.append(section)

    bracket_list_list.append(current_bracket_list)

    return bracket_list_list

# ================================= Tactic-lists =================================
#
# With a bracket-list as input, we want to retrieve a list of Rocq tactics.
#
# Our output will be a list of `chains`.
# A chain is a list of tactics linked by ";" that terminates with a point ".".
# Inside of a chain, tactics are represented as simple Rocq tactics or as
# `brackets`.
# A bracket is a proof branching structure of the form "[... | ... | ...]".
# Inside of a bracket are `spaces`, blank spaces, or `sub-brackets` which are
# essentially chains that don't end with a point.
#
# For example, the string
#       "Proof.\nmove=> homGp freeG rT H.\nby apply/idP/idP=> [homHp|]; [apply: homGrp_trans homGp | apply: freeG].\nQed."
#
# translates to the bracket-list
#       ['Proof.\nmove=> homGp freeG rT H.\nby apply/idP/idP=> ', ['[homHp|]'], '; ', ['[apply: homGrp_trans homGp | apply: freeG]'], '.\nQed.']
#
# which itself translates to the (simplified) tactic-list
#       [Chain([Tactic('Proof')]),
#        Chain([Tactic('move=> homGp freeG rT H')]),
#        Chain([
#            Tactic('by apply/idP/idP=> [homHp|]'),
#            Bracket(
#               [Subbracket([Tactic('apply: homGrp_trans homGp')]),
#                Subbracket([Tactic('apply: freeG')])]
#            )
#        ]),
#        Chain([Tactic('Qed')])]
#
# ================================================================================

@dataclass
class Space():
    """Class for spaces inside of brackets."""
    blank: str

    def __str__(self):
        return self.blank

@dataclass
class Tactic():
    """Class for tactics inside of chains and sub-brackets."""
    lblank: str
    tactic: str
    rblank: str

    def __str__(self):
        return self.lblank + self.tactic + self.rblank

@dataclass
class Chain():
    """Class for chains."""
    tactics: list[Tactic]
    appendix: str = ""

    def __str__(self):
        return ";".join(map(str, self.tactics)) + "." + self.appendix

@dataclass
class Subbracket():
    """Class for sub-brackets."""
    tactics: list[Tactic]

    def __str__(self):
        return ";".join(map(str, self.tactics))

@dataclass
class Bracket():
    """Class for brackets."""
    lblank: str
    subtactics: list[Subbracket]
    rblank: str

    def __str__(self):
        return self.lblank + "[" + "|".join(map(str, self.subtactics)) + "]" + self.rblank

def bracket_list_to_sub_bracket(bracket_list):
    """Decompose a bracket-list into a sub-bracket."""
    tactic_pattern = re.compile(r"(?P<lblank>(\s|\\n)*)(?P<tactic>\S([\s\S])*\S)(?P<rblank>(\s|\\n)*)")

    tactic_list = []
    previous_text = ""
    for i, section in enumerate(bracket_list):

        # If we read a string, we split it with ";" as separator
        if isinstance(section, str):
            d = section.find(";")

            # The preceding content is not taken into account when spliting into tactics
            section = previous_text + section
            d = d + len(previous_text) if d >= 0 else -1

            while d >= 0:
                raw_tactic = section[:d]
                section = section[d+1:] if len(section) > d+1 else ""

                match = tactic_pattern.match(raw_tactic)
                tactic = Tactic(match.group("lblank"), match.group("tactic"), match.group("rblank"))
                tactic_list.append(tactic)

                d = section.find(";")

            previous_text = section

        # If we read a bracket, we'll look at what text comes before it
        elif isinstance(section, list):
            # If the previous text is blank, we have to check whether we encounter parantheses, braces or brackets
            if (previous_text + ' ').replace("\n", "").replace(" ", "") == "":

                first = section[0][0]
                # If we encounter parenthesis or braces, they are part of a tactic
                if first == '{' or first == '(':
                    previous_text += bracket_list_to_str(section)

                # If we encounter brackets, it means we start a proof branching structure
                elif first == '[':
                    bracket_list_list = split_bracket_list(copy_bracket_list(section))
                    sub_bracket_list = list(map(bracket_list_to_sub_bracket, bracket_list_list))

                    # Just end the bracket here if it terminates the bracket-list
                    if len(bracket_list) == i+1:
                        rblank = ""
                    else:
                        next_section = bracket_list[i+1]

                        # Now we can retrieve the separator ";" coming after the bracket
                        if isinstance(next_section, str):
                            d = next_section.find(";")

                            # If there is no separator, just end the bracket
                            if d == -1:
                                rblank = next_section
                                poss_next_section = ""
                            else:
                                rblank = next_section[:d]
                                poss_next_section = next_section[d+1:] if len(next_section) > d+1 else ""

                            # If there is some text between the bracket and the next separator, the bracket is part of some tactic
                            if not (rblank + ' ').replace("\n", "").replace(" ", "") == "":
                                previous_text += bracket_list_to_str(section)

                            else:
                                next_section = poss_next_section
                                bracket_list[i+1] = next_section

                                tactic = Bracket(previous_text, sub_bracket_list, rblank)
                                tactic_list.append(tactic)

                                previous_text = ""

                        # There is an issue if a bracket is directly followed by parentheses, braces or brackets
                        else:
                            raise Exception("Error: brackets are directly followed by some parentheses, braces or brackets.")

                # If the first character of a bracket is not an opening parenthesis, an opening brace or an opening bracket, there is a problem
                else:
                    raise Exception("Error: a bracket should start with an opening parenthesis, an opening brace or an opening bracket.")

            # If the text preceding a parenthesis, a brace or a bracket is not blank, the rest is part of some tactic
            else:
                previous_text += bracket_list_to_str(section)

    # If the remaining text is blank, check whether we have tactics or not
    if (previous_text + ' ').replace("\\n", "").replace(" ", "") == "":
        # If there is no tactics, we have just a space
        if len(tactic_list) == 0:
            return Space(previous_text)
        # Otherwise, just add the remaining blank text to the last tactics
        else:
            tactic_list[-1].rblank += previous_text
            return Subbracket(tactic_list)

    # If the remaining text is not blank, it is a tactic
    else:
        match = tactic_pattern.match(previous_text)
        tactic = Tactic(match.group("lblank"), match.group("tactic"), match.group("rblank"))
        tactic_list.append(tactic)
        return Subbracket(tactic_list)

def find_point(text):
    """Find the first point followed by a blank space (or nothing if it is the last character) in a text."""
    match = re.search(r"\.(\s|\\n)", text)

    if match:
        return match.start()
    elif len(text) > 0 and text[-1] == '.':
        return len(text) - 1
    else:
        return -1

def bracket_list_to_tactic_list(bracket_list):
    """Decompose a bracket-list into a tactic-list."""
    bracket_list = copy_bracket_list(bracket_list)
    tactic_pattern = re.compile(r"(?P<lblank>(\s|\\n)*)(?P<tactic>\S([\s\S])*\S)(?P<rblank>(\s|\\n)*)")

    tactic_list = []
    chain = []
    previous_text = ""
    previous_text_sep = "."
    for i, section in enumerate(bracket_list):

        # If we read a string, we split it with ";" and "." as separators
        if isinstance(section, str):
            p = find_point(section)
            s = section.find(";")

            # The preceding content is not taken into account when spliting into tactics
            section = previous_text + section
            p = p + len(previous_text) if p >= 0 else -1
            s = s + len(previous_text) if s >= 0 else -1

            # Next we split while we can
            sep = None
            while p >= 0 or s >= 0:
                # Find the first separator
                d = p if s == -1 else s if p == -1 else min(p, s)
                sep = "." if d == p else ";"

                raw_tactic = section[:d]
                section = section[d+1:] if len(section) > d+1 else ""

                # A point should not be taken into account if it is followed by a parenthesis, a brace or a bracket
                if sep == "." and len(section) == 0 and len(bracket_list) > i+1:
                    if isinstance(bracket_list[i+1], list):
                        section = raw_tactic + "."
                        break
                    else:
                        raise Exception("Error: a bracket should always come after a string part of a bracket-list.")

                else:
                    match = tactic_pattern.match(raw_tactic)
                    tactic = Tactic(match.group("lblank"), match.group("tactic"), match.group("rblank"))
                    chain.append(tactic)

                    # A point means the end of a chain
                    if sep == ".":
                        tactic_list.append(Chain(chain))
                        chain = []

                    p = find_point(section)
                    s = section.find(";")

            # Update the previous text and the previous text separator
            previous_text = section
            previous_text_sep = sep if sep else previous_text_sep

        # If we read a bracket, we'll look at what text comes before it
        elif isinstance(section, list):
            # If the previous text is blank, we have to check whether we encounter parantheses, braces or brackets
            if (previous_text + ' ').replace("\n", "").replace(" ", "") == "":

                first = section[0][0]
                # If we encounter parenthesis or braces, they are part of a tactic
                if first == '{' or first == '(':
                    previous_text += bracket_list_to_str(section)

                # If we encounter brackets, it means we start a proof branching structure
                elif first == '[':
                    # There must be a semicolon before a proof branching structure
                    if previous_text_sep == ";":
                        bracket_list_list = split_bracket_list(copy_bracket_list(section))
                        sub_bracket_list = list(map(bracket_list_to_sub_bracket, bracket_list_list))

                        # A proof cannot end with a proof branching structure
                        if len(bracket_list) == i+1:
                            raise Exception("Error: the proof is ending with a proof branching structure.")
                        else:
                            next_section = bracket_list[i+1]

                            # We look at the separator coming after the bracket
                            if isinstance(next_section, str):
                                p = find_point(next_section)
                                s = next_section.find(";")

                                # There is an issue if there is no separator
                                if p == -1 and s == -1:
                                    raise Exception("Error: there should always be a separator after brackets.")
                                else:
                                    d = p if s == -1 else s if p == -1 else min(p, s)
                                    sep = "." if d == p else ";"
                                    rblank = next_section[:d]

                                    # If there is some text between the bracket and the next separator, the bracket is part of some tactic
                                    if not (rblank + ' ').replace("\n", "").replace(" ", "") == "":
                                        previous_text += bracket_list_to_str(section)

                                    else:
                                        bracket_list[i+1] = next_section[d+1:] if len(next_section) > d+1 else ""

                                        tactic = Bracket(previous_text, sub_bracket_list, rblank)
                                        chain.append(tactic)

                                        # A point means the end of a chain
                                        if sep == ".":
                                            tactic_list.append(Chain(chain))
                                            chain = []

                                        previous_text = ""
                                        previous_text_sep = sep

                            # There is an issue if a bracket is directly followed by parentheses, braces or brackets
                            else:
                                raise Exception("Error: brackets are directly followed by some parentheses, braces or brackets.")

                    # If there is no ";" before a bracket, the bracket is part of some tactic
                    else:
                        previous_text += bracket_list_to_str(section)

                # If the first character of a bracket is not an opening parenthesis, an opening brace or an opening bracket, there is a problem
                else:
                    raise Exception("Error: a bracket should start with an opening parenthesis, an opening brace or an opening bracket.")

            # If the text preceding a parenthesis, a brace or a bracket is not blank, the rest is part of some tactic
            else:
                previous_text += bracket_list_to_str(section)

    # A proof must end with a point
    if len(previous_text) > 0 or len(chain) > 0:
        raise Exception("Error: the proof don't end with a point")
    else:
        return tactic_list

def tactic_list_to_str(tactic_list):
    """Flatten a tactic-list into a string."""
    return "".join(map(str, tactic_list))
