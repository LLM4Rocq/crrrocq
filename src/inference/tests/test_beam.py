import unittest
import os
import sys
from typing import List, Dict, Any, Optional

from pytanque import Pytanque

# Import the necessary classes
from ..agent import Parser, ToolHandler, MathProofAgent
from ..tools import Tool, ScriptTool, HaveTool
from ..llm import LLM



# Create a fake LLM class for testing beam search
class BeamSearchTestLLM(LLM):
    """A fake LLM that simulates different paths for beam search testing."""

    def __init__(self, beam_responses: List[List[str]]):
        """
        Initialize with a list of predefined response sequences for each beam.

        Args:
            beam_responses: List of response sequences, one sequence per beam
        """
        self.beam_responses = beam_responses
        self.call_counts = [0] * len(beam_responses)

    def generate(self, prompt: str, stop_sequences: Optional[List[str]] = None) -> str:
        """Return a predefined response for a single prompt."""
        if self.beam_responses and self.beam_responses[0]:
            response = self.beam_responses[0][0]
            self.beam_responses[0].pop(0)
            return response
        return ""

    def generate_batch(
        self, prompts: List[str], stop_sequences: Optional[List[str]] = None
    ) -> List[str]:
        """Return predefined responses for each prompt in the batch...."""
        responses = []

        for i, prompt in enumerate(prompts):
            if i < len(self.beam_responses) and self.call_counts[i] < len(
                self.beam_responses[i]
            ):
                responses.append(self.beam_responses[i][self.call_counts[i]])
                self.call_counts[i] += 1
            else:
                responses.append("")

        return responses


# Simple search tool for testing
class TestSearchTool(Tool):
    """A simple search tool for testing."""

    @property
    def name(self) -> str:
        return "search"

    @property
    def description(self) -> str:
        return "Search for information."
    
    @property
    def instruction(self) -> str:
        return "Search for information with a query in natural language."

    @property
    def tag(self) -> str:
        return "SEARCH"

    def run(self, input_text: str) -> Any:
        """Return a predefined search result."""
        return [f"Search result for: {input_text}"]


class TestBeamSearch(unittest.TestCase):
    """Test cases for beam search functionality."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures that are reused across all tests."""
        # Configure paths
        cls.workspace = os.path.abspath("examples")
        cls.file = "foo.v"

        # Create Pytanque instance
        cls.pet = Pytanque("127.0.0.1", 8765)
        cls.pet.connect()
        cls.pet.set_workspace(False, str(cls.workspace))

    def setUp(self):
        """Set up test fixtures before each test."""
        # Create tools
        self.search_tool = TestSearchTool()
        self.script_tool = ScriptTool(
            pet=self.pet,
            workspace=self.workspace,
            file=self.file,
            theorem="foo",
        )
        self.have_tool = HaveTool(
            pet=self.pet,
            workspace=self.workspace,
            file=self.file,
            theorem="foo",
        )

    def test_beam_search_first_path_succeeds(self):
        """Test beam search where the first path succeeds."""
        # Define beam responses - first path succeeds
        beam_responses = [
            [
                "Let me try this: <SCRIPT>intros n.</SCRIPT>",
                "<SCRIPT>lia.</SCRIPT>",
            ],  # First beam succeeds
            [
                "Let me try another approach: <SCRIPT>destruct n.</SCRIPT>",
                "<SCRIPT>simpl. lia.</SCRIPT>",
            ],  # Second beam also works but is slower
        ]

        # Create the test LLM
        test_llm = BeamSearchTestLLM(beam_responses)

        # Create agent
        agent = MathProofAgent(test_llm, self.search_tool, self.script_tool, self.have_tool)

        # Run proof with beam size 2
        result = agent.run_proof(beam_size=2)

        # Verify the proof succeeded and used the first path
        self.assertTrue(result.success)
        self.assertEqual(len(result.proof), 2)
        self.assertEqual(result.proof[0], "intros n.")
        self.assertEqual(result.proof[1], "lia.")

    def test_beam_search_second_path_succeeds(self):
        """Test beam search where the first path fails but the second succeeds."""
        # Define beam responses - first path fails, second succeeds
        beam_responses = [
            [
                "Let me try this: <SCRIPT>invalid_tactic.</SCRIPT>",
                "<SCRIPT>lia.</SCRIPT>",
            ],  # First beam fails
            [
                "Let me try another approach: <SCRIPT>intros n.</SCRIPT>",
                "<SCRIPT>lia.</SCRIPT>",
            ],  # Second beam succeeds
        ]

        # Create the test LLM
        test_llm = BeamSearchTestLLM(beam_responses)

        # Create agent
        agent = MathProofAgent(test_llm, self.search_tool, self.script_tool, self.have_tool)

        # Run proof with beam size 2
        result = agent.run_proof(beam_size=2)

        # Verify the proof succeeded using the second path
        self.assertTrue(result.success)
        self.assertEqual(len(result.proof), 2)
        self.assertEqual(result.proof[0], "intros n.")
        self.assertEqual(result.proof[1], "lia.")

    def test_beam_search_all_paths_fail(self):
        """Test beam search where all paths fail."""
        # Define beam responses - all paths fail
        beam_responses = [
            ["Let me try this: <SCRIPT>invalid_tactic1.</SCRIPT>"],  # First beam fails
            [
                "Let me try another approach: <SCRIPT>invalid_tactic2.</SCRIPT>"
            ],  # Second beam fails
        ]

        # Create the test LLM
        test_llm = BeamSearchTestLLM(beam_responses)

        # Create agent
        agent = MathProofAgent(test_llm, self.search_tool, self.script_tool, self.have_tool)

        # Run proof with beam size 2
        result = agent.run_proof(beam_size=2)

        # Verify the proof failed
        self.assertFalse(result.success)
        self.assertEqual(result.proof, [])

    def test_complex_beam_search(self):
        """Test beam search with more complex paths."""
        # Define beam responses - different approach paths
        beam_responses = [
            [  # First beam - indirect approach using lia
                "Let me try to solve it: <SCRIPT>intros n.</SCRIPT>",
                "blaL <SCRIPT>lia.</SCRIPT>",
            ],
            [  # Second beam - step by step approach
                "First, let's introduce the variable: <SCRIPT>intros n.</SCRIPT>",
                "Now, let's use induction: <SCRIPT>induction n.</SCRIPT>",
                "For the base case: <SCRIPT>simpl. lia.</SCRIPT>",
                "For the inductive case: <SCRIPT>simpl. lia.</SCRIPT>",
            ],
            [  # Third beam - different approach
                "Let's try with a case analysis: <SCRIPT>destruct n.</SCRIPT>",
                "For n=0: <SCRIPT>simpl. lia.</SCRIPT>",
                "For n=S n': <SCRIPT>simpl. lia.</SCRIPT>",
            ],
            [  # Last beam - direct approach using lia
                "Let me try to solve it directly: <SCRIPT>lia.</SCRIPT>",
            ],
        ]

        # Create the test LLM
        test_llm = BeamSearchTestLLM(beam_responses)

        # Create agent
        agent = MathProofAgent(test_llm, self.search_tool, self.script_tool, self.have_tool)

        # Run proof with beam size 4
        result = agent.run_proof(beam_size=4)

        # Verify that the proof succeeded with the first (shortest) path
        self.assertTrue(result.success)
        self.assertEqual(len(result.proof), 1)
        self.assertEqual(result.proof[0], "lia.")


if __name__ == "__main__":
    unittest.main()
