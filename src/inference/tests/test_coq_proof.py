import unittest
import os
import sys
from typing import List, Dict, Any, Optional

from pytanque import Pytanque

from ..prover_agent import CoqProofManager, ProverResult
from ..tools import ScriptTool


class TestCoqProofManager(unittest.TestCase):
    """Integration tests for the CoqProofManager class with real Coq prover tools."""

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

        # Create the proof manager
        self.manager = CoqProofManager(self.coq_tool)

    def test_initialization(self):
        """Test that the manager initializes correctly."""
        self.assertEqual(self.manager.coq_tool, self.coq_tool)
        self.assertEqual(self.manager.current_proof, self.coq_tool.env.thm_code)
        self.assertIn(self.coq_tool.tag, str(self.manager.script_pattern.pattern))

    def test_extract_script(self):
        """Test extracting a script from a response."""
        # Test with a valid script
        response = (
            f"Here's my solution: <{self.coq_tool.tag}>intros n.</{self.coq_tool.tag}>"
        )
        result = self.manager.extract_script(response)

        self.assertIsNotNone(result)
        self.assertEqual(result[0], "intros n.")

        # Test with no script
        response = "I'm not sure how to approach this."
        result = self.manager.extract_script(response)
        self.assertIsNone(result)

        # Test with multiple scripts (should find the first one)
        response = f"<{self.coq_tool.tag}>first tactic.</{self.coq_tool.tag}> Then <{self.coq_tool.tag}>second tactic.</{self.coq_tool.tag}>"
        result = self.manager.extract_script(response)
        self.assertEqual(result[0], "first tactic.")

    def test_process_response_with_valid_tactic(self):
        """Test processing a response with a valid tactic."""
        # Create a response with a valid tactic
        response = f"<{self.coq_tool.tag}>intros n.</{self.coq_tool.tag}>"

        # Process the response
        result = self.manager.process_response(
            response=response, coq_tool=self.coq_tool, verbose=False
        )

        # Check that the result is as expected
        self.assertTrue(result.success)
        self.assertFalse(result.is_complete)  # 'intros n' doesn't complete the proof
        self.assertIsNotNone(result.new_goals)
        self.assertIn("n  : nat", result.new_goals)
        self.assertIn("1 + n > n", result.new_goals)
        self.assertEqual(result.proof, ["intros n."])

    def test_process_response_with_invalid_tactic(self):
        """Test processing a response with an invalid tactic."""
        # Create a response with an invalid tactic
        response = f"<{self.coq_tool.tag}>invalid_tactic.</{self.coq_tool.tag}>"

        # Process the response
        result = self.manager.process_response(
            response=response, coq_tool=self.coq_tool, verbose=False
        )

        # Check that the result indicates an error
        self.assertFalse(result.success)
        self.assertFalse(result.is_complete)
        self.assertIsNone(result.new_goals)

    def test_process_response_completing_proof(self):
        """Test processing a response that completes the proof."""
        # Create a response with a tactic that completes the proof
        response = f"<{self.coq_tool.tag}>lia.</{self.coq_tool.tag}>"

        # Process the response
        result = self.manager.process_response(
            response=response, coq_tool=self.coq_tool, verbose=False
        )

        # Check that the result indicates a complete proof
        self.assertTrue(result.success)
        self.assertTrue(result.is_complete)
        self.assertIsNone(result.new_goals)  # No new goals when complete
        self.assertEqual(result.proof, ["lia."])

    def test_process_batch_responses(self):
        """Test processing a batch of responses."""
        # Create deep copies of the Coq tool for each response
        coq_tools = [self.coq_tool.deepcopy() for _ in range(3)]

        # Create responses with different tactics
        responses = [
            f"<{self.coq_tool.tag}>intros n.</{self.coq_tool.tag}>",  # Valid but incomplete
            f"<{self.coq_tool.tag}>invalid_tactic.</{self.coq_tool.tag}>",  # Invalid
            f"<{self.coq_tool.tag}>lia.</{self.coq_tool.tag}>",  # Valid and completes the proof
        ]

        # Process the batch
        result = self.manager.process_batch_responses(
            responses=responses, coq_tools=coq_tools, verbose=False
        )

        # Check that we got a successful result due to the third response
        self.assertIsNotNone(result)
        self.assertTrue(result.success)
        self.assertTrue(result.is_complete)
        self.assertEqual(result.proof, ["lia."])

    def test_process_batch_responses_no_success(self):
        """Test processing a batch of responses with no success."""
        # Create responses with different tactics that all fail
        responses = [
            f"<{self.coq_tool.tag}>invalid_tactic1.</{self.coq_tool.tag}>",  # Invalid
            f"<{self.coq_tool.tag}>invalid_tactic2.</{self.coq_tool.tag}>",  # Invalid
        ]

        # Create deep copies of the Coq tool for each response
        coq_tools = [self.coq_tool.deepcopy() for _ in range(len(responses))]

        # Process the batch
        result = self.manager.process_batch_responses(
            responses=responses, coq_tools=coq_tools, verbose=False
        )

        # Check that we got no successful result
        self.assertIsNone(result)

    def test_get_stop_sequences(self):
        """Test getting stop sequences."""
        stop_sequences = self.manager.get_stop_sequences()
        self.assertEqual(stop_sequences, [f"</{self.coq_tool.tag}>"])

    def test_get_initial_state(self):
        """Test getting the initial state."""
        # Get initial state with beam size 2
        coq_tools, active_indices = self.manager.get_initial_state(beam_size=2)

        # Check that we got the expected number of tools and indices
        self.assertEqual(len(coq_tools), 2)
        self.assertEqual(active_indices, [0, 1])

        # Check that the tools are different instances
        self.assertIsNot(coq_tools[0], coq_tools[1])

        # Check that the tools are initialized correctly
        self.assertEqual(coq_tools[0].env.thm, "foo")
        self.assertEqual(coq_tools[1].env.thm, "foo")

    def test_multi_step_proof(self):
        """Test a multi-step proof process."""
        # We'll simulate a multi-step proof process
        # Create a copy of the tool for this test
        coq_tool = self.coq_tool.deepcopy()

        # Step 1: Introduce variables
        response1 = f"<{self.coq_tool.tag}>intros n.</{self.coq_tool.tag}>"
        result1 = self.manager.process_response(
            response=response1, coq_tool=coq_tool, verbose=False
        )

        # Check the result of step 1
        self.assertTrue(result1.success)
        self.assertFalse(result1.is_complete)

        # Step 2: Apply lia to complete the proof
        response2 = f"<{self.coq_tool.tag}>lia.</{self.coq_tool.tag}>"
        result2 = self.manager.process_response(
            response=response2, coq_tool=coq_tool, verbose=False
        )

        # Check the result of step 2
        self.assertTrue(result2.success)
        self.assertTrue(result2.is_complete)

        # Check that the proof steps are correct
        self.assertEqual(coq_tool.env.proof, ["intros n.", "lia."])

    def test_foofoo_theorem(self):
        """Test with a different theorem (foofoo)."""
        # Create a ScriptTool for the 'foofoo' theorem
        foofoo_tool = ScriptTool(
            pet=self.pet,
            workspace=self.workspace,
            file=self.file,
            theorem="foofoo",
        )

        # Create a manager for this tool
        foofoo_manager = CoqProofManager(foofoo_tool)

        # Process a response that completes the proof
        response = f"<{foofoo_tool.tag}>lia.</{foofoo_tool.tag}>"
        result = foofoo_manager.process_response(
            response=response, coq_tool=foofoo_tool, verbose=False
        )

        # Check that the result indicates a complete proof
        self.assertTrue(result.success)
        self.assertTrue(result.is_complete)
        self.assertEqual(result.proof, ["lia."])

    def test_no_script_in_response(self):
        """Test processing a response with no script."""
        # Create a response with no script
        response = "I need to think about this problem some more..."

        # Process the response
        result = self.manager.process_response(
            response=response, coq_tool=self.coq_tool, verbose=False
        )

        # Check that the result indicates no script
        self.assertFalse(result.success)
        self.assertFalse(result.is_complete)
        self.assertIsNone(result.new_goals)


if __name__ == "__main__":
    unittest.main()
