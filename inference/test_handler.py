import unittest
import os
import sys
from typing import List, Dict, Any, Optional

# Add parent directory to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the necessary classes
from agent import Parser, ToolHandler
from tools import Tool, CoqProverTool
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

    @property
    def tag(self) -> str:
        return "SEARCH"

    def run(self, input_text: str) -> Any:
        """Return a predefined search result."""
        return [f"{input_text}", "another irrelevant lemma"]


class TestToolHandler(unittest.TestCase):
    """Test cases for the ToolHandler class."""

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
        """Set up test fixtures."""
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

        # Create a tool handler
        self.tools = {"search": self.search_tool, "coq-prover": self.coq_tool}
        self.handler = ToolHandler(self.parser, self.tools)

    def test_process_no_tool_calls(self):
        """Test processing text without any tool calls."""
        # Create a fake LLM that returns text with no tool calls
        fake_llm = FakeLLM("This is a simple response with no tool calls.")

        # Process the response
        result = self.handler.process_with_tools(fake_llm, "What is 2+2?")

        # The result should be the original text
        self.assertEqual(result, "This is a simple response with no tool calls.")

    def test_process_with_search_tool(self):
        """Test processing text with a search tool call."""
        # Create a fake LLM that returns text with a search tool call
        fake_llm = FakeLLM(
            "Let me search for that. <SEARCH>mathematics theorems</SEARCH>"
        )

        # Process the response
        result = self.handler.process_with_tools(
            fake_llm, "Tell me about math theorems"
        )

        # The result should include the tool call and result
        self.assertIn("<SEARCH>mathematics theorems</SEARCH>", result)
        self.assertIn("<RESULT>", result)

    def test_process_with_coq_tool(self):
        """Test processing text with a Coq prover tool call."""
        # Create a fake LLM that returns text with a Coq prover tool call
        fake_llm = FakeLLM(
            "Let me try to prove this theorem. <SCRIPT>intros n.</SCRIPT>"
        )

        # Process the response
        result = self.handler.process_with_tools(fake_llm, "Prove the foo theorem")

        # The result should include the tool call and result
        self.assertIn("<SCRIPT>intros n.</SCRIPT>", result)

    def test_process_with_multiple_tool_calls(self):
        """Test processing text with multiple tool calls in sequence."""
        # Create a fake LLM that sequentially returns responses with tool calls
        fake_llm = FakeLLM(
            [
                "Let me first search for information. <SEARCH>natural number theorems</SEARCH>",
                "Now I'll try to prove it. <SCRIPT>intros n.</SCRIPT>",
                "Let me finish the proof. <SCRIPT>lia.</SCRIPT>",
                "The proof is complete!",
            ]
        )

        # Process the response
        result = self.handler.process_with_tools(fake_llm, "Prove the foo theorem")

        # The result should include all tool calls and results
        self.assertIn("<SEARCH>natural number theorems</SEARCH>", result)
        self.assertIn("Search results:", result)
        self.assertIn("natural number theorems", result)
        self.assertIn("<SCRIPT>intros n.</SCRIPT>", result)
        self.assertIn("Goals: n  : nat\n⊢ 1 + n > n", result)
        self.assertIn("<SCRIPT>lia.</SCRIPT>", result)
        self.assertIn("<RESULT>\nNo more goals.\n</RESULT>", result)
        self.assertNotIn("The proof is complete!", result)

    def test_process_with_invalid_tool(self):
        """Test processing text with an invalid tool name."""
        # Create a fake LLM that returns text with an invalid tool call
        fake_llm = FakeLLM("Let me use a tool. <INVALID_TOOL>some input</INVALID_TOOL>")

        # Process the response
        result = self.handler.process_with_tools(fake_llm, "Use a tool")

        # The result should be the original text since the tool is not recognized
        self.assertEqual(
            result, "Let me use a tool. <INVALID_TOOL>some input</INVALID_TOOL>"
        )

    def test_process_with_failed_coq_tactic(self):
        """Test processing text with a Coq tactic that fails."""
        # Create a fake LLM that returns text with an invalid Coq tactic
        fake_llm = FakeLLM("Let me try this tactic. <SCRIPT>invalid_tactic.</SCRIPT>")

        # Process the response
        result = self.handler.process_with_tools(fake_llm, "Prove the foo theorem")

        # The result should include the tool call and error message
        self.assertIn("<SCRIPT>invalid_tactic.</SCRIPT>", result)
        self.assertIn("Error:", result)

    def test_process_with_complete_proof(self):
        """Test processing text with a complete proof."""
        # Create a fake LLM that returns text with a successful proof tactic
        fake_llm = FakeLLM("Let me prove this in one step. <SCRIPT>lia.</SCRIPT>")

        # Process the response
        result = self.handler.process_with_tools(fake_llm, "Prove the foo theorem")

        # The result should include the tool call and success message
        self.assertIn("<SCRIPT>lia.</SCRIPT>", result)
        self.assertIn("<RESULT>\nNo more goals.\n</RESULT>", result)

    def test_interleaved_conversation_with_tools(self):
        """Test a more realistic conversation with interleaved tool calls."""
        # Create a fake LLM with a sequence of responses simulating a conversation
        fake_llm = FakeLLM(
            [
                "I'll help you prove this theorem. First, let's understand what we're proving.\n\n"
                "<SEARCH>arithmetic inequality theorem nat</SEARCH>",
                "Based on the search results, we need to prove that adding 1 to a natural number "
                "makes it strictly greater. Let's start the proof.\n\n"
                "<SCRIPT>intros n.</SCRIPT>",
                "Great! Now we've introduced the variable n. Next, we can apply a theorem from "
                "the standard library.\n\n"
                "<SCRIPT>lia.</SCRIPT>",
                "Perfect! We've completed the proof. The theorem 'foo' states that for any natural "
                "number n, 1 + n > n, which is a fundamental property of natural numbers.",
            ]
        )

        # Process the conversation
        result = self.handler.process_with_tools(
            fake_llm, "Can you help me prove the 'foo' theorem?"
        )

        # Verify the conversation flow and tool usage
        self.assertIn("<SEARCH>arithmetic inequality theorem nat</SEARCH>", result)
        self.assertIn("<SCRIPT>intros n.</SCRIPT>", result)
        self.assertIn("<SCRIPT>lia.</SCRIPT>", result)
        self.assertNotIn("Perfect! We've completed the proof.", result)


if __name__ == "__main__":
    unittest.main()
