# Mostly duplicating code from nlir

import re
import os
import copy
from abc import ABC, abstractmethod

from pytanque import Pytanque, State, Goal, PetanqueError


def pp_goal(g: Goal) -> str:
    """
    Pretty print one goal.
    """
    hyps = "\n".join(
        [
            f"{', '.join(h.names)} {':= ' + h.def_ if h.def_ else ''} : {h.ty}"
            for h in g.hyps
        ]
    )
    return f"{hyps}\n⊢ {g.ty}"


def pp_goals(gs: list[Goal]) -> str:
    """
    Pretty print a list of goals.
    """
    return "\n".join(pp_goal(g) for g in gs)


# def get_context(doc: str, thm: str) -> str:
#    """
#    Remove all proof to get context
#    """
#    pattern = r"Proof\.(.*?)(Qed|Admitted|Abort)\."
#    cleaned_text = re.sub(pattern, "", doc, flags=re.DOTALL)
#    # Replace multiple newlines with a single newline
#    cleaned_text = re.sub(r"\n+", "\n", cleaned_text)
#    lines = cleaned_text.split("\n")
#    for i, l in enumerate(lines):
#        if thm in l:
#            return "\n".join(lines[:i])
#    return cleaned_text


def get_context(doc: str, thm: str) -> str:
    """
    Remove all proof blocks to get context, but keep the theorem statement
    """
    pattern = r"Proof\.(.*?)(Qed|Admitted|Abort)\."
    cleaned_text = re.sub(pattern, "", doc, flags=re.DOTALL)
    # Replace multiple newlines with a single newline
    cleaned_text = re.sub(r"\n+", "\n", cleaned_text)
    lines = cleaned_text.split("\n")
    for i, l in enumerate(lines):
        if thm in l:
            # Find the end of the theorem statement by looking for the next empty line or "Proof."
            for j in range(i + 1, len(lines)):
                if lines[j].strip() == "" or lines[j].strip().startswith("Proof."):
                    # Return everything up to and including the theorem statement
                    return "\n".join(lines[:j])
            # If we don't find a clear end, just return up to and including this line
            return "\n".join(lines[: i + 1])
    return cleaned_text


class Env(ABC):
    """
    Base class for a Petanque environment.
    """

    def __init__(self, pet, workspace, file, thm, context=False, verbose=False):
        self.pet = pet
        self.workspace = workspace
        self.file = file
        self.path = os.path.join(workspace, file)
        self.thm = thm
        self.proof: list[str] = []
        self.initial_state: State = self.pet.start(self.path, thm)
        # self.thm_code = pp_goals(self.pet.goals(self.initial_state))
        self.n_interactions = 0
        self.verbose = verbose
        self.failed = False
        if context:
            with open(self.path, "r") as read_file:
                self.context = get_context(read_file.read(), thm)
        else:
            self.context = ""

    @property
    @abstractmethod
    def proof_finished(self) -> bool:
        pass

    @abstractmethod
    def exec(self, response: str):
        pass

    @property
    @abstractmethod
    def new_goal_pp(self) -> str:
        pass

    def check_proof(self) -> bool:
        """
        Double check the proof, re-running all tactics from the initial state.
        """
        try:  # double check the proof
            s = self.initial_state
            for tac in self.proof:
                s = self.pet.run(s, tac)
            self.pet.run(s, "Qed.")
            return True
        except PetanqueError:
            return False

    def deepcopy(self):
        new = self.__class__(self.pet, self.workspace, self.file, self.thm)
        new.proof = copy.deepcopy(self.proof)
        new.n_interactions = copy.deepcopy(self.n_interactions)
        return new


class ScriptEnv(Env):
    def __init__(
        self,
        pet: Pytanque,
        workspace: str,
        file: str,
        thm: str,
        context=False,
        verbose=False,
    ):
        super().__init__(pet, workspace, file, thm, context, verbose)
        self.state: State = self.initial_state
        self.thm_code = pp_goals(self.pet.goals(self.state))
        self.added_tac = False
        self.previous_unsuccessful = []

    def exec(self, tactics):
        self.added_tac = False
        self.n_interactions += 1
        for tac in tactics:
            if self.verbose:
                print("tactic:", tac)
            try:
                self.state = self.pet.run(self.state, tac, timeout=10)
                self.proof.append(tac)
                self.added_tac = True
                self.previous_unsuccessful = []
                if self.verbose:
                    print("success")
            except PetanqueError as err:
                self.failed = True
                self.previous_unsuccessful.append(str(tac) + str(err.message))
                if self.verbose:
                    print("error:", err.message)
                break

    @property
    def new_goal_pp(self):
        return pp_goals(self.pet.goals(self.state))

    @property
    def proof_finished(self) -> bool:
        # Hack to bypass Petanque proof_finished flag
        try:
            self.pet.run(self.state, "Qed.")
            return True
        except PetanqueError:
            return False

    def deepcopy(self):
        new = super().deepcopy()
        new.state = copy.deepcopy(self.state)
        new.previous_unsuccessful = copy.deepcopy(self.previous_unsuccessful)
        return new
