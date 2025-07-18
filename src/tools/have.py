from typing import Tuple
from copy import deepcopy

from src.servers.script.client import PetClient, State, Goals, ClientError
from .base import BaseTool, ToolError

class HaveTool(BaseTool):
    """Tool for interacting with the Coq theorem prover."""

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

    def run(self, have: str, agent=None, **kwargs) -> str:
        """
        Duplicate the current agent
        """
        assert agent, "No MathAgent provided."
        try:
            new_agent = agent.duplicate(reset_blocks=True)
            initial_goals = deepcopy(new_agent.tools['script'].goals)

            new_agent.tools['script'].run(have)
            new_agent.run_proof(initial_goals=initial_goals)
            new_agent.transfertools(agent)
            goals = new_agent.tools['script'].goals
            return "The goal to prove is:\n" + goals[0]['pp']
        except Exception as e:
            raise ToolError(e.message) from e
        
