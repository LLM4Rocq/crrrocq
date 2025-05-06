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

def lemma_from_goal(init_hyps, goal):
    """Provided base hypotheses and a goal, returns a lemma corresponding to the goal. The base hypotheses are supposed to be variables already in the context at the beginning of the proof."""

    lemma = "Lemma goal "
    for hyp in goal.hyps:
        hyp_names = [n for n in hyp.names if not n in init_hyps]
        if len(hyp_names) > 0:
            lemma += "(" + " ".join(hyp_names)
            lemma += (" := " + hyp.def_ if hyp.def_ else "")
            lemma += " : " + hyp.ty + ") "
    lemma += ": " + goal.ty + "."

    return lemma

def separate_haves(pet, theorem_name, theorem_path, tactic_list):
    init = False

    # A list of special case:
    #     homGrp_trans
    special_case = [False]

    new_tactic_list = []
    new_chain = []
    in_have = False
    i = 0
    while i < len(tactic_list):
        tactic = tactic_list[i]

        # Iter through the tactics of the chain
        for tac in tactic.tactics:

            # We look if we are proving a have or not
            if not in_have:

                # If we have a tactic, we scan it using some regex
                if isinstance(tac, tactics.Tactic):

                    # We check if tac is possibly a `have` or not
                    match = re.search(r"(|-|\+|gen|by|\*)(\s|\\n)*have", str(tac))
                    if match and match.start() == 0:

                        # We remove the `let ... in` inside of tac because they hinder us from reading tac properly
                        str_tac = str(tac)
                        match = re.search(r"let[\s\S]*?in", str_tac)
                        while match:
                            str_tac = str_tac[:match.start()] + str_tac[match.end():]
                            match = re.search(r"let[\s\S]*?in", str_tac)

                        # We check if tac is a `have` introducing an expression or not
                        if not re.search(r"have[\s\S]*?:=", str_tac):

                            # We check if there is a by after the have
                            if not re.search(r"have[\s\S]*?by", str(tac)):

                                # If we have not yet initialized the states, we do it now
                                if not init:

                                    init_state = pet.start(theorem_path, theorem_name) # State at the beginning of the proof
                                    dummy_state = pet.run_tac(init_state, "admit. Lemma dummy : true = true. ") # Dummy state to retrieve a goal with only variables and parameters as hypotheses
                                    dummy_goals = pet.goals(dummy_state) # The dummy goals
                                    if len(dummy_goals) != 1:
                                        raise Exception("Error: there should be only one goal at the beginning.")
                                    dummy_goal = dummy_goals[0]

                                    # Get the variables and parameters
                                    init_hyps = []
                                    for hyp in dummy_goal.hyps:
                                        for n in hyp.names:
                                            init_hyps.append(n)

                                    base_state = pet.run_tac(init_state, tactics.tactic_list_to_str(new_tactic_list))
                                    init = True

                                # Compute the goals before applying tac
                                current_proof = str(tactics.Chain(new_chain)) if len(new_chain) > 0 else ""
                                state = pet.run_tac(base_state, current_proof)
                                goals_before = pet.goals(state)

                                # Compute the goals after applying tac
                                current_proof = str(tactics.Chain(new_chain + [tac]))
                                state = pet.run_tac(base_state, current_proof)
                                goals_after = pet.goals(state)

                                # Retrieve the new goals
                                new_goals = goals_after[:len(goals_after) - len(goals_before)]

                                # If there is no new goals, tac is considered as a simple tactic
                                if len(new_goals) == []:
                                    new_chain.append(tac)

                                # Otherwise, we can start looking for the proof of the new goals introduced by tac
                                else:
                                    in_have = True
                                    tac.lblank = tac.lblank + "(*<have>*) "
                                    goals = { "have": tac, "tactic_list": [], "prev": goals_before, "prev_tactic_list": [], "new": new_goals, "new_tactic_list": [] }

                            # If there is a by after the have, the proof of the have is included in tac
                            else:
                                new_chain.append(tactics.Tactic(tac.lblank + "(*<have>*) ", tac.tactic, " (*</have>*)" + tac.rblank))

                        # If it is a have introducing an expression, tac is considered as a simple tactic
                        else:
                            new_chain.append(tac)

                    # If there is no have, tac is a simple tactic
                    else:
                        new_chain.append(tac)

                elif isinstance(tac, tactics.Bracket):
                    new_chain.append(tac)

                else:
                    raise Exception("Error: inside of a chain, there is only tactics and brackets")

            # If we are proving a have
            else:
                goals["tactic_list"].append(tac)

                # If tac is a tactic, we try to apply it to previous and new goals
                if isinstance(tac, tactics.Tactic):
                    ntacs = [tac] * len(goals["new"])
                    ntac = tac
                    ptacs = [tac] * len(goals["prev"])
                    ptac = tac

                # If tac is a bracket, we apply each sub-bracket to the goal it corresponds
                elif isinstance(tac, tactics.Bracket):
                    if len(tac.subtactics) != len(goals["new"]) + len(goals["prev"]):
                        raise Exception("Error: the number of proof in a proof branching structure should always match the number of goals.")
                    ntacs = tac.subtactics[:len(goals["new"])]
                    ntac = tactics.Bracket(tac.lblank, ntacs, tac.rblank)
                    ptacs = tac.subtactics[len(goals["new"]):]
                    ptac = tactics.Bracket(tac.lblank, ptacs, tac.rblank)

                # Update the previous goals by applying the corresponding tactics to them
                pgoals = []
                for pgoal, tac in zip(pgoals, ptacs):
                    state = pet.run_tac(init_state, lemma_from_goal(init_hyps, pgoal) + str(tac) + ".")
                    pgoals += pet.goals(state)
                goals["prev_tactic_list"].append(ptac)
                goals["prev"] = pgoals

                # Update the new goals by applying the corresponding tactics to them
                ngoals = []
                for ngoal, tac in zip(ngoals, ntacs):
                    state = pet.run_tac(init_state, lemma_from_goal(init_hyps, ngoal) + str(tac) + ".")
                    ngoals += pet.goals(state)
                goals["new_tactic_list"].append(ntac)
                goals["new"] = ngoals

                # We check if the proof of have is finished
                if len(goals["new"]) == 0:
                    in_have = False

                    # Create a `have ... by` tactic
                    have_by = goals["have"]
                    have_by.tactic += " by "
                    have_by.tactic += ";".join(map(str, goals["new_tactic_list"]))
                    have_by.rblanck = " (*</have>*)" + have_by.rblank

                    # Add the tactics for previous goals to the current chain
                    new_chain += goals["prev_tactic_list"]

                    # Add the `have ... by` tactic to the current chain
                    new_chain.append(have_by)

        # At the end of a chain, we check if we are in a proof of a have or not
        nnew_tactic_list = []
        if in_have:

            # To end the proof of have, we apply chains until there is no new goals left
            i += 1
            while i < len(tactic_list) and len(goals["new"]) > 0:
                goal = goals["new"][0]
                goals["new"] = goals["new"][1:]

                # We handle special cases
                if goal.ty.find("and_rel x1 x2 r = (x1 == x2) && r") >= 0 or special_case[0]:
                    special_case[0] = True
                    for hyp in goal.hyps:
                        hyp.ty = hyp.ty.replace("and_rel x1 x2 r = (x1 == x2) && r", "and_rel x1 x2 r = (x1 == x2) && r :> bool")
                        hyp.ty = hyp.ty.replace("and_rel x0 x3 r0 = (x0 == x3) && r0", "and_rel x0 x3 r0 = (x0 == x3) && r0 :> bool")
                    goal.ty = goal.ty.replace("and_rel x1 x2 r = (x1 == x2) && r", "and_rel x1 x2 r = (x1 == x2) && r :> bool")
                    goal.ty = goal.ty.replace("and_rel x0 x3 r0 = (x0 == x3) && r0", "and_rel x0 x3 r0 = (x0 == x3) && r0 :> bool")

                # Compute the new goals
                state = pet.run_tac(init_state, lemma_from_goal(init_hyps, goal) + str(tactic_list[i]))
                new_goals = pet.goals(state)
                nnew_tactic_list.append(tactic_list[i])
                goals["new"] = new_goals + goals["new"]

                i += 1

            # The proof of the have is finished
            in_have = False

            # Add the tactics for previous goals to the current chain
            new_chain += goals["prev_tactic_list"]

            # Add the have to the current chain
            new_chain.append(goals["have"])

            # Add the tactics for new goals to the current chain
            new_chain += goals["new_tactic_list"]

            # Add the tag at the end of the proof of have
            nnew_tactic_list[-1].appendix = " (*</have>*)"

        else:
            i += 1

        # Update the new tactic-list with the new tactics
        tactic_list_increment = [tactics.Chain(new_chain)] + nnew_tactic_list
        new_tactic_list += tactic_list_increment
        new_chain = []

        # If we have a base state, update it
        if init:
            proof_increment = tactics.tactic_list_to_str(tactic_list_increment)
            base_state = pet.run_tac(base_state, proof_increment)

    return new_tactic_list
