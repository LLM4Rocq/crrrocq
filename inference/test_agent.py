import unittest
import os
import sys
from typing import List, Dict, Any, Optional

# Add parent directory to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the necessary classes
from agent import Parser, ToolHandler, MathProofAgent, Status
from tools import Tool, CoqProverTool, SearchTool
from llm import LLM
from pytanque import Pytanque


# Create a fake LLM class for testing
class FakeLLM(LLM):
    """A fake LLM that returns predefined responses for testing."""

    def __init__(self, responses=None):
        """
        Initialize with a list of predefined responses.

        Args:
            responses: List of strings to return in sequence,
                       or a single string to always return
        """
        if responses is None:
            self.responses = ["Default response"]
        elif isinstance(responses, str):
            self.responses = [responses]
        else:
            self.responses = list(responses)

        self.call_count = 0

    def generate(self, prompt: str, stop_sequences: Optional[List[str]] = None) -> str:
        """Return the next predefined response."""
        if self.call_count < len(self.responses):
            response = self.responses[self.call_count]
            self.call_count += 1
            return response
        else:
            return "No more responses available."


# Create a simple search tool for testing
class FakeSearchTool(Tool):
    """A fake search tool for testing."""

    @property
    def name(self) -> str:
        return "search"

    @property
    def description(self) -> str:
        return "Search for information."

    def run(self, input_text: str) -> Any:
        """Return a predefined search result."""
        return [f"Search result for: {input_text}", "another relevant theorem"]


class TestMathProofAgent(unittest.TestCase):
    """Test cases for the MathProofAgent class."""

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
        # Create a parser
        self.parser = Parser()

        # Create tools
        self.search_tool = FakeSearchTool()
        self.coq_tool = CoqProverTool(
            pet=self.pet,
            workspace=self.workspace,
            file=self.file,
            theorem="foo",
        )

        # Need to reset the Coq tool before each test
        self.coq_tool.reset()

    def test_agent_initialization(self):
        """Test proper initialization of the MathProofAgent."""
        # Create a fake LLM
        fake_llm = FakeLLM("Test response")

        # Create an agent
        agent = MathProofAgent(fake_llm, self.search_tool, self.coq_tool)

        # Check if it was initialized correctly
        self.assertEqual(agent.llm, fake_llm)
        self.assertEqual(len(agent.tools), 2)
        self.assertIn(self.search_tool.name, agent.tools)
        self.assertIn(self.coq_tool.name, agent.tools)
        self.assertIsNotNone(agent.tool_handler)
        self.assertIsNotNone(agent.current_proof)

    def test_build_prompt(self):
        """Test prompt building functionality."""
        # Create a fake LLM
        fake_llm = FakeLLM("Test response")

        # Create an agent
        agent = MathProofAgent(fake_llm, self.search_tool, self.coq_tool)

        # Build a prompt
        prompt = agent.build_prompt()

        # Verify prompt content
        self.assertIn("You are a formal mathematics proving assistant", prompt)
        self.assertIn("<SEARCH>", prompt)
        self.assertIn("<SCRIPT>", prompt)
        self.assertIn(self.search_tool.name, prompt)
        self.assertIn(self.coq_tool.name, prompt)
        self.assertIn(self.search_tool.description, prompt)
        self.assertIn(self.coq_tool.description, prompt)
        self.assertIn("forall n : nat, 1 + n > n", prompt)  # The foo theorem

    def test_run_proof_success(self):
        """Test running a proof that succeeds."""
        # Create a fake LLM that will make a successful proof
        fake_llm = FakeLLM("Let me solve this. <SCRIPT>lia.</SCRIPT>")

        # Create an agent
        agent = MathProofAgent(fake_llm, self.search_tool, self.coq_tool)

        # Run the proof
        result = agent.run_proof()

        # Check if the proof succeeded
        self.assertTrue(result.success)
        self.assertIn("lia.", result.proof)

    def test_run_proof_failure(self):
        """Test running a proof that fails."""
        # Create a fake LLM that will make an invalid proof attempt
        fake_llm = FakeLLM("Let me try this. <SCRIPT>invalid_tactic.</SCRIPT>")

        # Create an agent
        agent = MathProofAgent(fake_llm, self.search_tool, self.coq_tool)

        # Run the proof
        result = agent.run_proof()

        # Check if the proof failed
        self.assertFalse(result.success)
        # The proof list should be empty since the tactic failed
        self.assertEqual(result.proof, [])

    def test_run_proof_with_search(self):
        """Test running a proof that uses search and then applies tactics."""
        # Create a fake LLM that will search and then apply tactics
        fake_llm = FakeLLM(
            [
                "Let me search for relevant theorems. <SEARCH>arithmetic inequalities</SEARCH>",
                "Based on the search results, I'll use lia. <SCRIPT>lia.</SCRIPT>",
            ]
        )

        # Create an agent
        agent = MathProofAgent(fake_llm, self.search_tool, self.coq_tool)

        # Run the proof
        result = agent.run_proof()

        # Check if the proof succeeded
        self.assertTrue(result.success)
        self.assertIn("lia.", result.proof)

    def test_multi_step_proof(self):
        """Test running a proof with multiple steps."""
        # Create a fake LLM that will execute multiple tactics
        fake_llm = FakeLLM(
            [
                "First, let's introduce the variable. <SCRIPT>intros n.</SCRIPT>",
                "Now, let's apply arithmetic reasoning. <SCRIPT>lia.</SCRIPT>",
            ]
        )

        # Create an agent
        agent = MathProofAgent(fake_llm, self.search_tool, self.coq_tool)

        # Run the proof
        result = agent.run_proof()

        # Check if the proof succeeded
        self.assertTrue(result.success)
        self.assertEqual(len(result.proof), 2)
        self.assertEqual(result.proof[0], "intros n.")
        self.assertEqual(result.proof[1], "lia.")

    def test_verbose_mode(self):
        """Test running in verbose mode."""
        # Create a fake LLM
        fake_llm = FakeLLM("Let me solve this. <SCRIPT>lia.</SCRIPT>")

        # Create an agent
        agent = MathProofAgent(fake_llm, self.search_tool, self.coq_tool)

        # Run the proof with verbose output (capturing stdout)
        import io
        from contextlib import redirect_stdout

        f = io.StringIO()
        with redirect_stdout(f):
            result = agent.run_proof(verbose=True)

        # Check if verbose output was generated
        output = f.getvalue()
        self.assertIn("LLM Response:", output)

    def test_foofoo_theorem(self):
        """Test proving a different theorem (foofoo)."""
        # Create a different Coq tool for the foofoo theorem
        foofoo_tool = CoqProverTool(
            pet=self.pet,
            workspace=self.workspace,
            file=self.file,
            theorem="foofoo",
        )

        # Create a fake LLM
        fake_llm = FakeLLM("This is a bit harder. <SCRIPT>lia.</SCRIPT>")

        # Create an agent
        agent = MathProofAgent(fake_llm, self.search_tool, foofoo_tool)

        # Run the proof
        result = agent.run_proof()

        # Check if the proof succeeded
        self.assertTrue(result.success)
        self.assertIn("lia.", result.proof)

    def test_complex_proof_strategy(self):
        """Test a more complex proof strategy with multiple iterations."""
        # Create a fake LLM with a sequence of responses simulating a complex proof
        fake_llm = FakeLLM(
            [
                "Let me think about this problem. <SEARCH>arithmetic inequality tactics</SEARCH>",
                "Based on the search results, I'll first introduce the variable. <SCRIPT>intros n.</SCRIPT>",
                "Now I need to consider the cases. <SCRIPT>destruct n.</SCRIPT>",
                "For the base case, it's simple. <SCRIPT>simpl. lia.</SCRIPT>",
                "For the inductive case, let's use our arithmetic solver. <SCRIPT>lia.</SCRIPT>",
            ]
        )

        # Create an agent
        agent = MathProofAgent(fake_llm, self.search_tool, self.coq_tool)

        # Run the proof
        result = agent.run_proof()

        # The proof should succeed and contain all the tactics
        self.assertTrue(result.success)
        self.assertTrue(
            len(result.proof) >= 3
        )  # At least 3 tactics should have been applied

    def test_agent_with_real_search_tool(self):
        """Test the agent with a more realistic search tool."""
        # Create a more realistic search tool
        real_search = SearchTool()

        # Create a fake LLM
        fake_llm = FakeLLM(
            [
                "Let me search for relevant information. <SEARCH>Coq arithmetic inequalities</SEARCH>",
                "Now I'll apply what I found. <SCRIPT>lia.</SCRIPT>",
            ]
        )

        # Create an agent
        agent = MathProofAgent(fake_llm, real_search, self.coq_tool)

        # Run the proof
        result = agent.run_proof()

        # The proof should succeed
        self.assertTrue(result.success)
        self.assertIn("lia.", result.proof)


if __name__ == "__main__":
    unittest.main()
