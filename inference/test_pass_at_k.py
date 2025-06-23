import unittest
import os
import sys
from typing import List, Dict, Any, Optional

# Add parent directory to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pass_at_k_prover import PassAtKProver
from prover_agent import CoqProofManager, ProverResult
from tools import ScriptTool
from llm import VLLM
from pytanque import Pytanque


# Mock VLLM class for testing
class MockVLLM(VLLM):
    """A mock implementation of VLLM for testing."""

    def __init__(self, responses=None):
        """
        Initialize with predefined responses.

        Args:
            responses: Dictionary mapping prompts to responses, or list of responses to return in sequence
        """
        self.responses = responses or {}
        self.response_list = []
        if isinstance(responses, list):
            self.response_list = responses
        self.calls = []
        self.prompts = []
        self.verbose = False

    def build_prompt(
        self, theorem_code: str, script_tag: str, goals_tag: str = "GOALS"
    ) -> str:
        """Build a simple prompt for testing."""
        prompt = f"<{goals_tag}>{theorem_code}</{goals_tag}>"
        return prompt

    def generate(self, prompt: str, stop_sequences: Optional[List[str]] = None) -> str:
        """Return a predefined response for the prompt."""
        self.calls.append(("generate", prompt, stop_sequences))
        self.prompts.append(prompt)

        if self.response_list:
            # Return responses in sequence
            if len(self.calls) <= len(self.response_list):
                return self.response_list[len(self.calls) - 1]
            return "No more responses"
        else:
            # Return response from dictionary
            return self.responses.get(prompt, "Default response")

    def generate_batch(
        self, prompts: List[str], stop_sequences: Optional[List[str]] = None
    ) -> List[str]:
        """Return predefined responses for each prompt."""
        self.calls.append(("generate_batch", prompts, stop_sequences))
        self.prompts.extend(prompts)

        if self.response_list:
            # Calculate starting index based on previous calls
            start_idx = sum(
                1 for call in self.calls[:-1] if call[0] == "generate_batch"
            )
            start_idx = start_idx * len(prompts)
            # Return responses in sequence for this batch
            return [
                (
                    self.response_list[start_idx + i]
                    if start_idx + i < len(self.response_list)
                    else "No more responses"
                )
                for i in range(len(prompts))
            ]
        else:
            # Return responses from dictionary
            return [
                self.responses.get(prompt, "Default response") for prompt in prompts
            ]


class TestPassAtKProver(unittest.TestCase):
    """Integration tests for the PassAtKProver class using a real pet-server."""

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
        # Create a ScriptTool for the 'foo' theorem
        self.coq_tool = ScriptTool(
            pet=self.pet,
            workspace=self.workspace,
            file=self.file,
            theorem="foo",
        )

        # Reset the Coq tool before each test
        self.coq_tool.reset()

    def test_initialization(self):
        """Test that the prover initializes correctly."""
        # Create a mock VLLM
        mock_llm = MockVLLM()

        # Create the prover
        prover = PassAtKProver(
            llm=mock_llm, coq_tool=self.coq_tool, k=3, max_iterations=5, verbose=False
        )

        # Verify initialization
        self.assertEqual(prover.llm, mock_llm)
        self.assertEqual(prover.k, 3)
        self.assertEqual(prover.max_iterations, 5)
        self.assertFalse(prover.verbose)
        self.assertEqual(prover.goals_tag, "GOALS")
        self.assertEqual(prover.result_tag, "r")

    def test_custom_tags(self):
        """Test initialization with custom tags."""
        # Create a mock VLLM
        mock_llm = MockVLLM()

        # Create the prover with custom tags
        prover = PassAtKProver(
            llm=mock_llm,
            coq_tool=self.coq_tool,
            goals_tag="CUSTOM_GOALS",
            result_tag="custom_result",
        )

        # Verify custom tags
        self.assertEqual(prover.goals_tag, "CUSTOM_GOALS")
        self.assertEqual(prover.result_tag, "custom_result")

    def test_successful_proof_for_foo_theorem(self):
        """Test finding a successful proof for the 'foo' theorem."""
        # Create a mock VLLM with responses that solve the 'foo' theorem
        mock_llm = MockVLLM(
            [
                f"<{self.coq_tool.tag}>lia.</{self.coq_tool.tag}>"  # Response that solves 'foo' directly
            ]
        )

        # Create the prover with k=1 (single path)
        prover = PassAtKProver(
            llm=mock_llm, coq_tool=self.coq_tool, k=1, max_iterations=5, verbose=False
        )

        # Run the prover
        success, proof = prover.run_pass_at_k()

        # Verify the result
        self.assertTrue(success)
        self.assertEqual(proof, ["lia."])

    def test_multi_step_proof(self):
        """Test a proof that requires multiple steps."""
        # Create a mock VLLM with responses that form a multi-step proof
        mock_llm = MockVLLM(
            [
                f"<{self.coq_tool.tag}>intros n.</{self.coq_tool.tag}>",  # First step
                f"<{self.coq_tool.tag}>lia.</{self.coq_tool.tag}>",  # Second step
            ]
        )

        # Create the prover with k=1 (single path)
        prover = PassAtKProver(
            llm=mock_llm, coq_tool=self.coq_tool, k=1, max_iterations=5, verbose=False
        )

        # Run the prover
        success, proof = prover.run_pass_at_k()

        # Verify the result
        self.assertTrue(success)
        self.assertEqual(proof, ["intros n.", "lia."])

    def test_pass_at_k_with_multiple_paths(self):
        """Test pass@k with multiple paths."""
        # Create responses for 3 parallel paths, with only the last one succeeding
        responses = [
            # First iteration
            f"<{self.coq_tool.tag}>invalid_tactic.</{self.coq_tool.tag}>",  # Path 1 (fails)
            f"<{self.coq_tool.tag}>intros n.</{self.coq_tool.tag}>",  # Path 2 (progresses)
            f"<{self.coq_tool.tag}>lia.</{self.coq_tool.tag}>",  # Path 3 (succeeds directly)
            # Second iteration (not used for path 3 since it already succeeded)
            f"<{self.coq_tool.tag}>still_invalid.</{self.coq_tool.tag}>",  # Path 1 (still fails)
            f"<{self.coq_tool.tag}>lia.</{self.coq_tool.tag}>",  # Path 2 (completes the proof)
        ]

        # Create a mock VLLM with these responses
        mock_llm = MockVLLM(responses)

        # Create the prover with k=3 (three parallel paths)
        prover = PassAtKProver(
            llm=mock_llm, coq_tool=self.coq_tool, k=3, max_iterations=5, verbose=False
        )

        # Run the prover
        success, proof = prover.run_pass_at_k()

        # Verify the result
        self.assertTrue(success)
        self.assertEqual(proof, ["lia."])  # Path 3 completed in one step

        # Verify that we only needed one iteration (path 3 succeeds in first batch)
        self.assertEqual(len(mock_llm.calls), 1)

    def test_max_iterations_reached(self):
        """Test when max iterations is reached without finding a proof."""
        # Create a mock VLLM with responses that don't solve the theorem
        mock_llm = MockVLLM(
            [
                f"<{self.coq_tool.tag}>invalid_tactic1.</{self.coq_tool.tag}>",
                f"<{self.coq_tool.tag}>invalid_tactic2.</{self.coq_tool.tag}>",
            ]
        )

        # Create the prover with max_iterations=2
        prover = PassAtKProver(
            llm=mock_llm, coq_tool=self.coq_tool, k=1, max_iterations=2, verbose=False
        )

        # Run the prover
        success, proof = prover.run_pass_at_k()

        # Verify the result
        self.assertFalse(success)
        self.assertEqual(proof, [])

        # Verify that we tried both iterations
        self.assertEqual(len(mock_llm.calls), 2)

    def test_with_foofoo_theorem(self):
        """Test with a different theorem (foofoo)."""
        # Create a ScriptTool for the 'foofoo' theorem
        foofoo_tool = ScriptTool(
            pet=self.pet,
            workspace=self.workspace,
            file=self.file,
            theorem="foofoo",
        )

        # Create a mock VLLM with response that solves 'foofoo'
        mock_llm = MockVLLM(
            [
                f"<{foofoo_tool.tag}>lia.</{foofoo_tool.tag}>"  # Response that solves 'foofoo'
            ]
        )

        # Create the prover
        prover = PassAtKProver(
            llm=mock_llm, coq_tool=foofoo_tool, k=1, max_iterations=5, verbose=False
        )

        # Run the prover
        success, proof = prover.run_pass_at_k()

        # Verify the result
        self.assertTrue(success)
        self.assertEqual(proof, ["lia."])


if __name__ == "__main__":
    unittest.main()
