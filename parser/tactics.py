
# ================================ Bracket-lists =================================
#
# With a string as input, we want to separate the parts that are enclosed in
# brackets, braces or square brackets from those that are not.
#
# Our output will be a list alternating between the parts of our input string
# inside and outside of brackets, braces or square brackets.
# Let's call such lists 'bracket-lists'.
#
# In a bracket-list, the parts outside parentheses are simply strings.
# The parts inside parentheses are stored as bracket-list to take into account the
# nesting of brackets.
#
# For example, the string
#       "Proof.\nby apply: (iffP (unitrP x)) => [[y []] | [y]]; exists y; rewrite // mulrC.\nQed."
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

    # As interval in math-comp are represented using square brackets,
    # we don't want to take these squared brackets into accounts
    # as they might no be closed: "`[0; +oo["
    backtic = False # Tells if the previous character is a backtic
    interval = False # Tells if we are reading an interval

    for c in string:

        # If we encounter a backtic outside of an interval, set backtic to true
        if not interval and c == '`':
            backtic = True
            add_char_to_bracket_list(bracket_list_list[-1], c)

        # If we encounter a square bracket and the previous character is a backtic, set interval to True to indicate we are reading an interval
        elif backtic and (c == '[' or c == ']'):
            backtic = False
            interval = True
            add_char_to_bracket_list(bracket_list_list[-1], c)

        # If we encounter a square bracket while reading an interval, set interval to False to indicate we have finished reading an interval
        elif interval and (c == '[' or c == ']'):
            interval = False
            add_char_to_bracket_list(bracket_list_list[-1], c)

        # If we encounter an opening bracket character, we start the construction of a new bracket-list
        elif c == '[' or c == '{' or c == '(':
            backtic = False
            bracket_list_list.append([c])

        # If we encounter a closing bracket character, we close the current bracket-list
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
