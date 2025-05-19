import re
from typing import Optional, Tuple
from dataclasses import dataclass
from pytanque import Pytanque, State, PetanqueError

from .chains import Tactic, BranchTactic, Chain, copy_chain_list, chain_list_to_str, proof_to_chain_list

# ==================================== haves =====================================
#
# Given a chain-list (see chains.py) as input, we return a new chain-list where
# `have` tactics and their proof have been enclosed in `(*<have>*)` and
# `(*</have>*)` tags.
#
# For example, the proof
#
#       Proof.
#       rewrite join_subG !subsetI sHG subsetIl /=; apply/andP; split.
#         apply/subsetP=> h Hh /[1!inE]; have Gh := subsetP sHG h Hh.
#         apply/subsetP=> W _; have simW := socle_simple W; have [modW _ _] := simW.
#         have simWh: mxsimple rH (socle_base W *m rG h) by apply: Clifford_simple.
#         rewrite inE -val_eqE /= PackSocleK eq_sym.
#         apply/component_mx_isoP; rewrite ?subgK //; apply: component_mx_iso => //.
#         by apply: submx_trans (component_mx_id simW); move/mxmoduleP: modW => ->.
#       apply/subsetP=> z cHz /[1!inE]; have [Gz _] := setIP cHz.
#       apply/subsetP=> W _; have simW := socle_simple W; have [modW _ _] := simW.
#       have simWz: mxsimple rH (socle_base W *m rG z) by apply: Clifford_simple.
#       rewrite inE -val_eqE /= PackSocleK eq_sym.
#       by apply/component_mx_isoP; rewrite ?subgK //; apply: Clifford_iso.
#       Qed.
#
# is rewritten as
#
#       Proof.
#       rewrite join_subG !subsetI sHG subsetIl /=; apply/andP; split.
#         apply/subsetP=> h Hh /[1!inE]; have Gh := subsetP sHG h Hh.
#         apply/subsetP=> W _; have simW := socle_simple W; have [modW _ _] := simW.
#         (*<have>*) have simWh: mxsimple rH (socle_base W *m rG h) by apply: Clifford_simple (*</have>*).
#         rewrite inE -val_eqE /= PackSocleK eq_sym.
#         apply/component_mx_isoP; rewrite ?subgK //; apply: component_mx_iso => //.
#         by apply: submx_trans (component_mx_id simW); move/mxmoduleP: modW => ->.
#       apply/subsetP=> z cHz /[1!inE]; have [Gz _] := setIP cHz.
#       apply/subsetP=> W _; have simW := socle_simple W; have [modW _ _] := simW.
#       (*<have>*) have simWz: mxsimple rH (socle_base W *m rG z) by apply: Clifford_simple (*</have>*).
#       rewrite inE -val_eqE /= PackSocleK eq_sym.
#       by apply/component_mx_isoP; rewrite ?subgK //; apply: Clifford_iso.
#       Qed.
#
# ================================================================================

def is_have_tactic(tactic: str) -> bool:
    """Check if the given tactic is an interesting have."""

    # Check if there is a valid [have] in the tactic
    match = re.search(r"(|-|\+|gen|by|\*)\s*have", tactic)
    if not match or match.start() != 0:
        return False

    # Remove all [let ... in] from the tactic
    match = re.search(r"let[\s\S]*?in", tactic)
    while match:
        tactic = tactic[:match.start()] + tactic[match.end():]
        match = re.search(r"let[\s\S]*?in", tactic)

    # Remove all [:=:] from the tactic
    i = tactic.find(":=:")
    while i >= 0:
        tactic = tactic[:i] + tactic[i+3:]
        i = tactic.find(":=:")

    # Check if we have [have ... := ...] or [have ... : ...]
    if re.search(r"have[\s\S]*?:=", tactic):
        return False

    return True

def is_have_by_tactic(tactic: str) -> bool:
    """Check if the given tactic contains `have ... by`."""
    return re.search(r"have[\s\S]*?by", tactic)

def flexible_run_tac(pet: Pytanque, state: State, code: str, is_have_by: bool) -> Tuple[bool, State]:
    """Run the code on some state with a pet instance.
    If `is_have_by` is true, then Petanque errors are allowed."""

    try:
        state = pet.run_tac(state, code)
        success = True
    except PetanqueError as err:
        success = False
        if not is_have_by:
            raise err

    return success, state

open_tag = "(*<have>*) "
close_tag = " (*</have>*)"

def enclose_haves(pet: Pytanque, name: str, path: str, chain_list: list[Chain]) -> Tuple[bool, list[Chain]]:
    chain_list = copy_chain_list(chain_list)
    init = False

    new_chain_list = []
    new_chain = []
    in_have_proof = False
    i = 0
    while i < len(chain_list):
        old_chain = chain_list[i]

        # Iter through the tactics of the old chain
        for tactic in old_chain.tactics:

            # Check if we are in a have proof or not
            if not in_have_proof:
                if isinstance(tactic, Tactic) and is_have_tactic(str(tactic)):
                    is_have_by = is_have_by_tactic(str(tactic))

                    # Start the proof checking if it had not been initialized yet
                    # (made to avoid using the pet-server if it is not necessary)
                    if not init:
                        base_state = pet.start(path, name)
                        base_state_checkpoint = 0
                        init = True

                    # Update the base state so it represents the state of the proof at the chain before the one we are checking
                    base_state = pet.run_tac(base_state, chain_list_to_str(new_chain_list[base_state_checkpoint:]))
                    base_state_checkpoint = len(new_chain_list)
                    # Compute the number of goals at this point
                    nbr_previous_goals = len(pet.goals(base_state))

                    # Look at the number of goals introduced between the start of the chain and the have tactic
                    if len(new_chain) > 0:
                        state = pet.run_tac(base_state, str(Chain(new_chain, '.')))
                        nbr_inter_goals = len(pet.goals(state)) - nbr_previous_goals
                    else:
                        nbr_inter_goals = 0

                    # If there is no new goals introduced, it means the previous part of the chain is focusing on the top goal
                    # We can split the current chain in two: first the previous part of the chain, then the part after the have
                    if nbr_inter_goals == 0:
                        # We compute the number of goals introduced by the have tactic (it should always be one)
                        success, state = flexible_run_tac(pet, base_state, str(Chain(new_chain + [tactic], '.')), is_have_by)
                        nbr_new_goals = len(pet.goals(state)) - nbr_previous_goals

                        # Because a [have ... by] can fail and return the previous state, we must check thouroughly if the tactic is proven on the spot or not
                        # If the run_tac ended with a success, the proof of the [have ... by] tactic is contained in it
                        if is_have_by and success:
                            # Add the opening tag just before the tactic
                            k = 0
                            while tactic.tactic[k].isspace():
                                k += 1
                            tactic.tactic = tactic.tactic[:k] + open_tag + tactic.tactic[k:] + close_tag

                        # If the run_tac ended without a success, the proof of the [have ... by] needs to be continued
                        # The proof must also be continued if new goals are introduced
                        elif (is_have_by and not success) or nbr_new_goals > 0:
                            # Add the opening tag just before the tactic
                            k = 0
                            while tactic.tactic[k].isspace():
                                k += 1
                            tactic.tactic = tactic.tactic[:k] + open_tag + tactic.tactic[k:]

                            # We start the have proof
                            in_have_proof = True

                    # If there is new goals introduced by the first part of the chain,
                    # we consider the set up to be too complicated to handle
                    # and we proceed as if the have tactic was a normal tactic
                    # In fact, this case never happens
                    elif nbr_inter_goals > 0:
                        tactic.tactic = "(*<have2complex>*) " + tactic.tactic + " (*</have2complex>*)"

                    else:
                        raise Exception("Error: the have tactic is applied on a closed goal.")

                new_chain.append(tactic)

            # If we are in the proof of a have, we have to look if the proof ends within the current chain
            else:

                # If we encounter a branch, the first sub-chain should target the top goal before the have, and the rest of the sub-chains should target the goals introduced after the have tactic
                if isinstance(tactic, BranchTactic):
                    if len(tactic.chains) != 1 + nbr_new_goals:
                        raise Exception("Error: a bracket does not contain the right amount of sub-goals.")
                    # The first sub-goal can be put before the have and removed from the bracket
                    tactic.chains[0].suffix = '.'
                    new_chain_list.append(tactic.chains[0])
                    tactic.chains = tactic.chains[1:]

                success, state = flexible_run_tac(pet, base_state, str(Chain(new_chain + [tactic], '.')), is_have_by)
                nbr_new_goals = len(pet.goals(state)) - nbr_previous_goals

                # If we have finished the proof, just add the proof to the new chain-list, update the base state and reset the new chain
                if (not is_have_by or success) and nbr_new_goals == 0:
                    new_chain.append(tactic)
                    new_chain_list.append(Chain(new_chain, '.' + close_tag))
                    base_state = state
                    base_state_checkpoint += 1
                    new_chain = []
                    in_have_proof = False

                # Otherwise, continue searching for the proof
                elif (is_have_by and not success) or nbr_new_goals > 0:
                    new_chain.append(tactic)

                else:
                    raise Exception("Error: some tactic closed the have goal and the following goal.")

        # If we are still searching for the proof of the have at the end of the chain, we look for the proof in the following chains
        if in_have_proof:

            # Update the new chain-list and the base state
            new_chain_list.append(Chain(new_chain, '.'))
            base_state = pet.run_tac(base_state, str(Chain(new_chain, '.')))
            base_state_checkpoint += 1
            new_chain = []

            # While we have not finished the have proof, we look at following chains, updating the new chain-list and the base state at each chain
            i += 1
            while i < len(chain_list) and nbr_new_goals > 0:
                base_state = pet.run_tac(base_state, str(chain_list[i]))
                base_state_checkpoint += 1
                new_goals = pet.goals(base_state)
                nbr_new_goals = len(new_goals) - nbr_previous_goals
                new_chain_list.append(chain_list[i])

                i += 1

            in_have_proof = False

            # We add the tag at the end of the proof
            new_chain_list[-1].suffix += close_tag

        # If we are not in a have proof at the end of a chain, we simply go on to the next chain
        else:
            if len(new_chain) > 0:
                new_chain_list.append(Chain(new_chain, '.'))
                new_chain = []
            i += 1

    return init, new_chain_list

# ====================
# Parsing
# ====================

@dataclass
class HaveTactic:
    prefix: str
    intro: str
    statement: str
    infix: str
    proof: str
    suffix: str

    def __str__(self):
        return self.prefix + self.intro + self.statement + self.infix + self.proof + self.suffix

    def no_proof(self):
        return self.prefix + self.intro + self.statement + " [...] " + self.suffix

def parse_have_tags(text: str) -> Optional[re.Match]:
    """Search for have tags in a text."""
    pattern = re.compile(f"(?<prefix>)\\s*{open_tag}\\s*)(?<body>[\\s\\S]*?)(?<suffix>\\s*{close_tag}\\s*)")
    return pattern.search(text)

def parse_have_tactics(text: str) -> list:
    """Parse all have tactics in some text."""
    parsed_text = []
    pattern = re.compile(r"(?<intro>[\s\S]*?:\s*)(?<statement>[\s\S]*?)(?<infix>\s*(\.\s|;|by)\s*)(?<proof>[\s\S]*)")

    match = parse_have_tags(text)
    while match:
        if match.start() > 0:
            parsed_text.append(text[:match.start()])
        prefix, body, suffix = match.group("prefix"), match.group("body"), match.group("suffix")
        bmatch = pattern.match(body)
        have_tactic = HaveTactic(prefix, bmatch.group("intro"), bmatch.group("statement"), bmatch.group("infix"), bmatch.group("proof"), suffix)
        text = text[match.end():]
        match = parse_have_tags(text)

    if len(text) > 0:
        parsed_text.append(text)
    return parsed_text

# ====================
# Construction
# ====================

import json
import argparse
from tqdm import tqdm
from pathlib import Path

# Theorems from math-comp raising an error:
#
# nz2                    Some notation is unknown in the scope
# leqif_mul              A have with a trivial proof appears in a by chain
# redivp_eq              Two theorems are defined with the same name in the same file, only one of the two is taken into account
# rdivpp                 Two theorems are defined with the same name in the same file, only one of the two is taken into account
# edivpP                 Two theorems are defined with the same name in the same file, only one of the two is taken into account
# edivp_eq               Two theorems are defined with the same name in the same file, only one of the two is taken into account
# dvdpP                  Two theorems are defined with the same name in the same file, only one of the two is taken into account
# coprimepP              Two theorems are defined with the same name in the same file, only one of the two is taken into account
# modpZl                 Two theorems are defined with the same name in the same file, only one of the two is taken into account
# divpZl                 Two theorems are defined with the same name in the same file, only one of the two is taken into account
# modpD                  Two theorems are defined with the same name in the same file, only one of the two is taken into account
# divpD                  Two theorems are defined with the same name in the same file, only one of the two is taken into account
# divp_pmul2l            Two theorems are defined with the same name in the same file, only one of the two is taken into account
# divp_divl              Two theorems are defined with the same name in the same file, only one of the two is taken into account
# divpZr                 Two theorems are defined with the same name in the same file, only one of the two is taken into account
# normN1                 Two theorems are defined with the same name in the same file, only one of the two is taken into account
# exprNn_pchar           A definition overshadow this theorem
# exprDn_pchar           A definition overshadow this theorem
# invrM                  A definition overshadow this theorem
# invrZ                  A definition overshadow this theorem
# eq_holds               A definition overshadow this theorem
# prim_order_exists      A definition overshadow this theorem

def make(dataset: str, petanque_address: str, petanque_port: int):
    """Enclose all the have with a proof of a dataset."""

    datafile = Path(dataset)
    dataset = dataset.split("_", maxsplit=1)[0]
    if not datafile.exists():
        raise Exception(f"Error: {datafile} doesn't exist.")
    savefile = Path(datafile.parent, datafile.stem + "_have.jsonl")
    if not savefile.exists():
        savefile.touch()

    pet = Pytanque(petanque_address, petanque_port)
    pet.connect()

    theorems = []
    with open(datafile, "r") as f:
        for line in f:
            theorems.append(json.loads(line))

    theorems_with_have = []
    with open(savefile, "r") as f:
        for line in f:
            theorems_with_have.append(json.loads(line))

    _theorems_with_have = [(t["name"], t["filepath"], t["statement"]) for t in theorems_with_have]
    theorems_without_have = [t for t in theorems if not (t["name"], t["filepath"], t["statement"]) in _theorems_with_have]

    f = open(savefile, "a")

    error_theorems = []
    for theorem in tqdm(theorems_without_have):
        name = theorem["name"]
        path = Path(dataset, theorem["filepath"])
        proof = theorem["proof"]
        chain_list = proof_to_chain_list(proof)

        try:
            modified, chain_list = enclose_haves(pet, name, path, chain_list)
            reproof = chain_list_to_str(chain_list)

            if modified:
                state = pet.start(path, name)
                pet.run_tac(state, reproof)
            else:
                assert (proof == reproof)

            theorem["proof"] = reproof
            f.write(json.dumps(theorem) + '\n')
        except PetanqueError as err:
            error_theorems.append(name + " -> " + err.message)
        except Exception as err:
            error_theorems.append(name + " -> " + err.args[0])

    f.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enclose all have with a proof in a dataset of theorems.")
    parser.add_argument("--dataset", type=str, default="../math-comp_bm25.jsonl", help="The name or path to the dataset, default is '../math-comp_bm25.jsonl'")
    parser.add_argument("--address", type=str, default="127.0.0.1", help="Address of the petanque server, default is '127.0.0.1'")
    parser.add_argument("--port", type=int, default=8765, help="Port of the petanque server, default is 8765")
    args = parser.parse_args()
    make(args.dataset, args.address, args.port)
