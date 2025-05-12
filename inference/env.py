# Mostly duplicating code from nlir

import re
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from collections import deque
from typing import Iterable, Union, Tuple
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


class Env(ABC):
    """
    Base class for a Petanque environment.
    """

    def __init__(self, pet, workspace, file, thm, verbose=False):
        self.pet = pet
        self.workspace = workspace
        self.file = file
        self.path = os.path.join(workspace, file)
        self.thm = thm
        self.proof: list[str] = []
        self.initial_state: State = self.pet.start(self.path, thm)
        #self.thm_code = pp_goals(self.pet.goals(self.initial_state))
        self.n_interactions = 0
        self.verbose = verbose
        self.failed = False

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
                s = self.pet.run_tac(s, tac)
            self.pet.run_tac(s, "Qed.")
            return True
        except PetanqueError:
            return False

    def deepcopy(self):
        new = self.__class__(
            self.pet, self.workspace, self.file, self.thm, self.verbose
        )
        new.proof = copy.deepcopy(self.proof)
        new.n_interactions = copy.deepcopy(self.n_interactions)
        return new


class ScriptEnv(Env):
    def __init__(self, pet: Pytanque, workspace: str, file: str, thm: str):
        super().__init__(pet, workspace, file, thm)
        self.state: State = self.initial_state
        self.thm_code = pp_goals(self.pet.goals(self.state))

    def exec(self, tactics):
        self.n_interactions += 1
        for tac in tactics:
            if self.verbose:
                print("tactic:", tac)
            try:
                self.state = self.pet.run_tac(self.state, tac, timeout=10)
                self.proof.append(tac)
                if self.verbose:
                    print("success")
            except PetanqueError as err:
                self.failed = True
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
            self.pet.run_tac(self.state, "Qed.")
            return True
        except PetanqueError:
            return False

    def deepcopy(self):
        new = super().deepcopy()
        new.state = copy.deepcopy(self.state)
        return new
