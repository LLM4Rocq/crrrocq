import re
from pytanque import PetanqueError

import tactics

# ==================================== haves =====================================
#
# Given a tactic-list (see tactics.py) as input, we return a new tactic-list where
# `have` tactics and their proof have been enclosed in `(*<have>*)` and
# `(*</have>*)` comments.
#
# ================================================================================

# TODO: correct the function !!!!!!!

def enclose_haves(pet, name, path, tactic_list):
    init = False

    new_tactic_list = []
    new_chain = []
    in_have = False
    i = 0
    while i < len(tactic_list):
        tactic = tactic_list[i]

        # Iter through the tactics of the chain
        for j, tac in enumerate(tactic.tactics):

            # Check if we are in a have proof or not
            if not in_have:
                if isinstance(tac, tactics.Tactic):

                    # Check if the tactic has to be treated as a have
                    match = re.search(r"(|-|\+|gen|by|\*)(\s|\\n)*have", str(tac))
                    if match and match.start() == 0:

                        # Remove all the let ... in
                        str_tac = str(tac)
                        match = re.search(r"let[\s\S]*?in", str_tac)
                        while match:
                            str_tac = str_tac[:match.start()] + str_tac[match.end():]
                            match = re.search(r"let[\s\S]*?in", str_tac)

                        # Remove all the :=:
                        idx = str_tac.find(":=:")
                        while idx >= 0:
                            str_tac = str_tac[:idx] + str_tac[idx+3:]
                            idx = str_tac.find(":=:")

                        # Check if the have use := or :, if it use :, there is a proof for the have statement
                        if not re.search(r"have[\s\S]*?:=", str_tac):

                            # Check if there is a by in the tactic, if there is not, the proof of the have is done in the following tactics
                            if not re.search(r"have[\s\S]*?by", str(tac)):

                                # Start the proof checking if it had not been initialized yet
                                # (made to avoid using the pet-server if it is not necessary)
                                if not init:
                                    base_state = pet.start(path, name)
                                    base_state_checkpoint = 0
                                    init = True

                                # Update the base state so it represents the state of the proof at the chain before the one we are checking
                                base_state = pet.run_tac(base_state, tactics.tactic_list_to_str(new_tactic_list[base_state_checkpoint:]))
                                base_state_checkpoint = len(new_tactic_list)
                                # Compute the number of goals at this point
                                nbr_previous_goals = len(pet.goals(base_state))

                                # Look at the number of goals introduced between the start of the chain and the have tactic
                                if len(new_chain) > 0:
                                    state = pet.run_tac(base_state, str(tactics.Chain(new_chain)))
                                    nbr_inter_goals = len(pet.goals(state)) - nbr_previous_goals
                                else:
                                    nbr_inter_goals = 0

                                # If there is no new goals introduced, it means the previous part of the chain is focusing on the top goal
                                # We can split the current chain in two: first the previous part of the chain, then the part after the have
                                if nbr_inter_goals == 0:
                                    # We compute the number of goals introduced by the have tactic (it should always be one)
                                    state = pet.run_tac(base_state, str(tactics.Chain(new_chain + [tac])))
                                    nbr_new_goals = len(pet.goals(state)) - nbr_previous_goals

                                    # If for some reason there is no new goals introduced by the have tactic,
                                    # we continue as if the have tactic was a normal tactic
                                    if nbr_new_goals > 0:

                                        # If there is a previous part to the chain, we add it to the new tactic-list and compute the new base state
                                        if len(new_chain) > 0:
                                            new_tactic_list.append(tactics.Chain(new_chain))
                                            base_state = pet.run_tac(base_state, str(tactics.Chain(new_chain)))
                                            base_state_checkpoint += 1
                                            new_chain = []

                                        # We start the have proof
                                        tac.lblank = tac.lblank + "(*<have>*) "
                                        in_have = True

                                    new_chain.append(tac)

                                # If there is new goals introduced by the first part of the chain,
                                # we consider the set up to be too complicated to handle
                                # and we proceed as if the have tactic was a normal tactic
                                elif nbr_inter_goals > 0:
                                    new_chain.append(tactics.Tactic(tac.lblank + "(*<have2complex>*) ", tac.tactic, " (*</have2complex>*)" + tac.rblank))

                                else:
                                    raise Exception("Error: the have tactic is applied on a closed goal.")

                            # If there is a by in the tactic, the proof of the have is necessarily made of the remaining part of the chain
                            else:
                                tac.lblank = tac.lblank + "(*<have>*) "
                                tactic.tactic_list[-1].rblank = " (*</have>*)" + tactic.tactic_list[-1].rblank
                                new_chain += tactic.tactic_list[j:]
                                break

                        # If it is a have followed by :=, there is no proof and it should be considered a normal tactic
                        else:
                            new_chain.append(tac)

                    # If the tactic does not contain have, we continue iterating through the tactics
                    else:
                        new_chain.append(tac)

                # If the tactic is a bracket, we continue iterating through the tactics
                elif isinstance(tac, tactics.Bracket):
                    new_chain.append(tac)

                else:
                    raise Exception("Error: a chain contains something else than tactics and brackets.")

            # If we are in the proof of a have, we have to look if the proof ends within the current chain
            else:

                # If we encounter a bracket, the first sub-goal should target the top goal before the have, and the rest of the sub-goal should target the goals introduced after the have tactic
                if isinstance(tac, tactics.Bracket):
                    if len(tac.subtactics) != 1 + nbr_new_goals:
                        raise Exception("Error: a bracket does not contain the right amount of sub-goals.")
                    # The first sub-goal can be put before the have and removed from the bracket
                    new_tactic_list.append(tactics.Chain(tac.subtactics[0].tactics))
                    tac.subtactics = tac.subtactics[1:]

                state = pet.run_tac(base_state, str(tactics.Chain(new_chain + [tac])))
                nbr_new_goals = len(pet.goals(state)) - nbr_previous_goals

                # If we have finished the proof, just add the proof to the new tactic-list, update the base state and reset the new chain
                if nbr_new_goals == 0:
                    new_chain.append(tac)
                    new_chain.appendix = " (*</have>*)"
                    new_tactic_list.append(tactics.Chain(new_chain))
                    base_state = state
                    base_state_checkpoint += 1
                    new_chain = []
                    in_have = False

                # Otherwise, continue searching for the proof
                elif nbr_new_goals > 0:
                    new_chain.append(tac)

                else:
                    raise Exception("Error: some tactic closed the have goal and the following goal.")

        # If we are still searching for the proof of the have at the end of the chain, we look for the proof in the following chains
        if in_have:

            # Update the new tactic-list and the base state
            new_tactic_list.append(tactics.Chain(new_chain))
            base_state = pet.run_tac(base_state, str(tactics.Chain(new_chain)))
            base_state_checkpoint += 1
            new_chain = []

            # While we have not finished the have proof, we look at following chains, updating the new tactic-list and the base state at each chain
            i += 1
            while i < len(tactics) and nbr_new_goals > 0:
                base_state = pet.run_tac(base_state, str(tactics[i]))
                base_state_checkpoint += 1
                new_goals = pet.goals(base_state)
                nbr_new_goals = len(new_goals)-nbr_previous_goals
                new_tactic_list.append(tactics[i])

                i += 1

            in_have = False

            # We add the tag at the end of the proof
            new_tactic_list[-1].appendix = " (*</have>*)"

        # If we are not in a have proof at the end of a chain, we simply go on to the next chain
        else:
            new_tactic_list.append(tactics.Chain(new_chain))
            new_chain = []
            i += 1

    return new_tactic_list
