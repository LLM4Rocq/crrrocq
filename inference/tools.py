from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union, Tuple
from dataclasses import dataclass

from env import ScriptEnv

# ===============================================
# Tool Interface
# ===============================================


class Tool(ABC):
    """Abstract base class for all tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the tool."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Return a description of what the tool does."""
        pass

    @property
    @abstractmethod
    def tag(self) -> str:
        """Return the XML tag name to use for this tool."""
        pass

    @abstractmethod
    def run(self, input_text: str) -> Any:
        """Execute the tool functionality."""
        pass


# ===============================================
# Tool Implementations
# ===============================================


class SearchTool(Tool):
    """Tool for searching relevant information."""

    @property
    def name(self) -> str:
        return "search"

    @property
    def description(self) -> str:
        return "Search for relevant mathematical theorems, definitions, or proofs."

    @property
    def tag(self) -> str:
        return "SEARCH"

    def run(self, query: str) -> List[str]:
        """
        Execute a search and return results.

        Note: This is a placeholder. Implement actual search functionality here.
        """
        # This would be replaced with actual search functionality
        return [f"Search result for: {query}"]


class CoqProverTool(Tool):
    """Tool for interacting with the Coq theorem prover."""

    def __init__(self, pet, workspace, file, theorem, context=False):
        """
        Initialize the Coq prover tool.

        Args:
            pet: Pytanque instance for interacting with Coq
            workspace: Path to the workspace directory
            file: Coq file name
            theorem: Name of the theorem to prove
            context: Whether to include context in output
        """
        self.pet = pet
        self.workspace = workspace
        self.file = file
        self.theorem = theorem
        self.env = ScriptEnv(pet, workspace, file, theorem, context=context)
        self.context = self.env.context

    @property
    def name(self) -> str:
        return "coq-prover"

    @property
    def description(self) -> str:
        return "Execute Coq tactics and return the new proof state or error."

    @property
    def tag(self) -> str:
        return "SCRIPT"

    def run(self, input_text: str) -> Dict[str, Any]:
        """
        Execute Coq tactics and return the result.

        Args:
            input_text: String containing Coq tactics, one per line

        Returns:
            Dictionary with status ('success' or 'error'), goal or error message
        """
        # Split the input into individual tactics
        tactics = [tac.strip() for tac in input_text.split("\n") if tac.strip()]

        try:
            # Execute the tactics
            self.env.exec(tactics)

            if self.env.failed and not self.env.added_tac:
                return {"status": "error", "message": "Tactic execution failed"}

            # Check if the proof is finished
            if self.env.proof_finished:
                return {
                    "status": "success",
                    "goal": "Proof completed",
                    "is_complete": True,
                }

            # Get the new proof state
            new_goal = self.env.new_goal_pp

            return {"status": "success", "goal": new_goal, "is_complete": False}

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def reset(self) -> None:
        """Reset the prover to the initial state."""
        self.env = ScriptEnv(self.pet, self.workspace, self.file, self.theorem)

    def deepcopy(self) -> "CoqProverTool":
        """Create a deep copy of the CoqProverTool instance."""
        new = self.__class__(self.pet, self.workspace, self.file, self.theorem)
        new.env = self.env.deepcopy()
        return new
