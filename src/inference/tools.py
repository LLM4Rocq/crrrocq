from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union, Tuple
from dataclasses import dataclass
import json
import faiss
import requests
import numpy as np

from .env import ScriptEnv
from .llm import LLM

# from src.embedding.models.base import BaseEmbedding
# from src.embedding.index.cosim_index import FaissIndex

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
    def instruction(self) -> str:
        """Return the instructions on how to use the tool."""
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

    def __init__(self, index_path, model, api_url, docstrings_path):
        super().__init__()
        self.index = faiss.read_index(index_path)
        self.model = model
        self.api_url = api_url
        self.docstrings_path = docstrings_path
        with open(docstrings_path, "r") as file:
            self.docstrings_dic = json.load(file)
        self.docstrings_keys = list(self.docstrings_dic.keys())

    @property
    def name(self) -> str:
        return "search"

    @property
    def description(self) -> str:
        return "Query for relevant existing theorems and lemmas"

    @property
    def instruction(self) -> str:
        return """### 🔍 Search Block  
**Purpose**: Discover relevant theorems and lemmas
- Query the theorem database with natural language descriptions
- Find existing results that support your proof strategy
- Identify patterns, equivalences, and useful properties
- **Best Practice**: Be specific in your search queries
"""

    @property
    def tag(self) -> str:
        return "search"

    def run(self, input_text: str, top_k=10) -> str:
        """
        Execute a search and return results.
        """
        response = requests.post(
            f"{self.api_url}/v1/embeddings",
            json={"model": self.model, "input": input_text},
        )

        text_embedding = response.json()["data"][0]["embedding"]
        print(np.array([text_embedding]).shape)
        distances, indices = self.index.search(
            np.array([text_embedding], dtype=np.float32), top_k
        )
        output = ""
        for i in indices[0]:
            key = self.docstrings_keys[i]
            element = self.docstrings_dic[key]
            fullname, docstring = element["fullname"], element["docstring"]
            output += f"{k}. {fullname}\n{docstring}\n\n"
        return {"content": output}


class ScriptTool(Tool):
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
        return "Executable Coq proof tactics and code"

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

            return {"status": "success", "is_complete": False, "goal": new_goal}

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def reset(self) -> None:
        """Reset the prover to the initial state."""
        self.env = ScriptEnv(self.pet, self.workspace, self.file, self.theorem)

    def deepcopy(self) -> "ScriptTool":
        """Create a deep copy of the ScriptTool instance."""
        new = self.__class__(self.pet, self.workspace, self.file, self.theorem)
        new.env = self.env.deepcopy()
        return new


class HaveTool(ScriptTool):
    @property
    def name(self) -> str:
        return "have-prover"

    @property
    def description(self) -> str:
        return "Intermediate lemma introduction"

    @property
    def instruction(self) -> str:
        return """### 🎯 Have Block
**Intermediate lemma creation**
- Introduce auxiliary goals using `have` tactics
- Break complex proofs into manageable subgoals
- **Constraint**: Must use valid `have` tactic syntax
- **Application**: Essential for multi-step mathematical arguments
"""

    @property
    def tag(self) -> str:
        return "have"
