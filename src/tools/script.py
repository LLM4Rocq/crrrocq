from typing import Tuple

from src.servers.script.client import PetClient, State, Goal, ClientError
from .base import BaseTool, ToolError

class ScriptTool(BaseTool):
    """Tool for interacting with the Coq theorem prover."""

    def __init__(self, base_url="", state=None):
        """
        Initialize the Coq prover tool.

        Args:
            pet: Pytanque instance for interacting with Coq
            workspace: Path to the workspace directory
            file: Coq file name
            theorem: Name of the theorem to prove
            context: Whether to include context in output
        """
        self.client = PetClient(base_url)
        self.state = state
    
    def start_thm(self, thm_name: str):
        """
        Initialize tool to start proving the given theorem
        """
        state, self.goals = self.client.start_thm(thm_name)
        self.state = {"pet_state": state, "login": self.client.login}

    @property
    def instruction(self) -> str:
        return """### ⚡ Script Block
**Purpose**: Execute Coq proof tactics
- Write valid Coq tactic sequences
- Apply theorems, perform rewrites, and manipulate goals
- **Requirement**: Code must be syntactically correct Coq
- **Output**: New proof state or error messages
"""

    @property
    def tag(self) -> str:
        return "script"

    def run(self, tactic: str, **kwargs) -> str:
        """
        Execute Coq tactic and return the result.
        """
        assert self.state, ToolError("No current state, start a theorem (start_thm) before using tool.")
        try:
            self.state, self.goals = self.client.run_tac(self.state, tactic)
            if self.goals:
                return "The goal to prove is:\n" + self.goals[0]['pp']
            else:
                return "No goals remaining, the proof is finished."
        except ClientError as e:
            raise ToolError(e.message) from e
        
