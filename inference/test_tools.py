import unittest
import os
import sys
from typing import List, Dict, Any

# Add parent directory to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the necessary classes
from tools import ScriptTool
from pytanque import Pytanque


class TestScriptToolIntegration(unittest.TestCase):
    """Integration tests for ScriptTool with a running pet-server."""

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

    def test_prove_foo_theorem_with_lia(self):
        """Test proving the 'foo' theorem using the 'lia' tactic."""
        # Create a tool instance for the 'foo' theorem
        tool = ScriptTool(
            pet=self.pet,
            workspace=self.workspace,
            file=self.file,
            theorem="foo",
        )

        # Run the 'lia' tactic which should prove the theorem
        result = tool.run("lia.")

        # Check that the proof was successful
        self.assertEqual(
            result["status"], "success", f"Expected success but got: {result}"
        )

        # The proof should be complete since 'lia' solves this theorem
        self.assertTrue(
            result.get("is_complete", False),
            f"Proof should be complete but got: {result}",
        )

    def test_prove_foofoo_theorem_with_lia(self):
        """Test proving the 'foofoo' theorem using the 'lia' tactic."""
        # Create a tool instance for the 'foofoo' theorem
        tool = ScriptTool(
            pet=self.pet,
            workspace=self.workspace,
            file=self.file,
            theorem="foofoo",
        )

        # Run the 'lia' tactic which should prove the theorem
        result = tool.run("lia.")

        # Check that the proof was successful
        self.assertEqual(
            result["status"], "success", f"Expected success but got: {result}"
        )

        # The proof should be complete since 'lia' solves this theorem
        self.assertTrue(
            result.get("is_complete", False),
            f"Proof should be complete but got: {result}",
        )

    def test_incremental_proof_foo_theorem(self):
        """Test an incremental proof of the 'foo' theorem."""
        # Create a tool instance for the 'foo' theorem
        tool = ScriptTool(
            pet=self.pet,
            workspace=self.workspace,
            file=self.file,
            theorem="foo",
        )

        # Step 1: Introduce variables
        result1 = tool.run("intros n.")
        self.assertEqual(result1["status"], "success", f"Intros failed: {result1}")
        self.assertFalse(
            result1.get("is_complete", True),
            "Proof should not be complete after intros",
        )

        # Step 2: Apply simple arithmetic
        result2 = tool.run("lia.")
        self.assertEqual(result2["status"], "success", f"Apply failed: {result2}")

        result3 = tool.run

        # The proof should now be complete
        self.assertTrue(
            result2.get("is_complete", False),
            f"Proof should be complete but got: {result2}",
        )

    def test_invalid_tactic(self):
        """Test using an invalid tactic."""
        # Create a tool instance for the 'foo' theorem
        tool = ScriptTool(
            pet=self.pet,
            workspace=self.workspace,
            file=self.file,
            theorem="foo",
        )

        # Run an invalid tactic
        result = tool.run("not_a_real_tactic.")

        # Check that the tactic failed
        self.assertEqual(result["status"], "error", f"Expected error but got: {result}")
        self.assertIn("message", result, "Error result should contain a message")

    def test_multiple_tactics_at_once(self):
        """Test running multiple tactics at once."""
        # Create a tool instance for the 'foo' theorem
        tool = ScriptTool(
            pet=self.pet,
            workspace=self.workspace,
            file=self.file,
            theorem="foo",
        )

        # Run multiple tactics
        result = tool.run("intros n.\ndestruct n.\n-\nlia.\n-\nlia.")

        # Check that all tactics executed successfully
        self.assertEqual(
            result["status"], "success", f"Expected success but got: {result}"
        )

        # The proof should be complete
        self.assertTrue(
            result.get("is_complete", False),
            f"Proof should be complete but got: {result}",
        )

    def test_reset_functionality(self):
        """Test the reset functionality."""
        # Create a tool instance for the 'foo' theorem
        tool = ScriptTool(
            pet=self.pet,
            workspace=self.workspace,
            file=self.file,
            theorem="foo",
        )

        # Run a tactic
        tool.run("intros n.")

        # Reset the environment
        tool.reset()

        # The goal should be back to the initial state
        result = tool.run("")  # Empty tactic to get current state

        # Check that we're back to the initial goal
        self.assertEqual(result["status"], "success")
        self.assertIn(
            "\n⊢ forall n : nat, 1 + n > n",
            result["goal"],
            "Goal should be reset to initial state",
        )


if __name__ == "__main__":
    unittest.main()
