from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any, Union
import re
import copy

from tools import ScriptTool
from llm import LLM


@dataclass
class ProverResult:
    """Result of processing an LLM response with the Coq prover."""

    success: bool = False
    # added_tac: bool = False
    is_complete: bool = False
    new_goals: str = None
    proof: List[str] = None
    previous_unsuccessful: List[str] = None


class CoqProofManager:
    """Manager for Coq theorem proving processes, focused on proof state manipulation."""

    def __init__(self, coq_tool: ScriptTool):
        """
        Initialize the proof manager with a Coq prover tool.

        Args:
            coq_tool: The Coq prover tool instance
        """
        self.coq_tool = coq_tool
        self.current_proof = coq_tool.env.thm_code
        # Create pattern for extracting Coq scripts using the tool's tag
        self.script_pattern = re.compile(
            f"<{coq_tool.tag}>(.*?)</{coq_tool.tag}>", re.DOTALL
        )

    def extract_script(self, text: str) -> Optional[Tuple[str, int, int]]:
        """
        Extract the Coq script from text.

        Args:
            text: The text to extract the script from

        Returns:
            Tuple of (script_content, start_position, end_position) or None if no script is found
        """
        match = self.script_pattern.search(text)
        if match:
            return (match.group(1).strip(), match.start(), match.end())
        return None

    def process_response(
        self,
        response: str,
        coq_tool: ScriptTool,
        verbose: bool = False,
    ) -> ProverResult:
        """
        Process a response: extract script, run it with Coq, and determine next steps.

        Args:
            response: The response text
            coq_tool: The Coq prover tool instance to use
            verbose: Whether to print verbose output

        Returns:
            ProverResult indicating success/failure and next steps
        """
        # Extract script from the response
        script_info = self.extract_script(response)

        if not script_info:
            # No script found in the response
            return ProverResult(
                proof=coq_tool.env.proof,
                new_goals=coq_tool.env.new_goal_pp,
                previous_unsuccessful=["Bad script format"],
            )

        script, _, _ = script_info

        # Run the script with the Coq tool
        result = coq_tool.run(script)

        if verbose:
            print("Script:", script, "Result:", result)

        # Check if the proof is complete
        if result["status"] == "success":
            if result.get("is_complete", False):
                # Proof is complete!
                return ProverResult(
                    success=True, is_complete=True, proof=coq_tool.env.proof
                )
            else:
                # Proof is progressing, include the new goals
                return ProverResult(
                    success=True,
                    # added_tac=coq_tool.env.added_tac,
                    is_complete=False,
                    new_goals=coq_tool.env.new_goal_pp,
                    proof=coq_tool.env.proof,
                    previous_unsuccessful=coq_tool.env.previous_unsuccessful,
                )
        else:
            # Script execution failed
            previous_unsuccessful = coq_tool.env.previous_unsuccessful
            coq_tool.env.previous_unsuccessful = []
            return ProverResult(
                proof=coq_tool.env.proof,
                new_goals=coq_tool.env.new_goal_pp,
                previous_unsuccessful=previous_unsuccessful,
            )

    def process_batch_responses(
        self,
        responses: List[str],
        coq_tools: List[ScriptTool],
        verbose: bool = False,
    ) -> Tuple[List[ProverResult], Optional[ProverResult]]:
        """
        Process a batch of responses with their corresponding tools.

        Args:
            responses: List of response texts
            coq_tools: List of Coq tools corresponding to each response
            verbose: Whether to print verbose output

        Returns:
            Tuple of (list of results, optional successful status)
            - If any proof completes successfully, the second item will be a Status
              with success=True and the proof steps
            - Otherwise, the second item will be None
        """
        results = []

        for i, (response, tool) in enumerate(zip(responses, coq_tools)):
            if verbose:
                print(f"Processing response {i}...")

            result = self.process_response(
                response=response,
                coq_tool=tool,
                verbose=verbose,
            )

            results.append(result)

            # If a proof is complete, return it immediately
            if result.success and result.is_complete:
                return results, result

        # No proof was completed
        return results, None

    def get_stop_sequences(self) -> List[str]:
        """
        Return the stop sequences needed for LLM generation.

        Returns:
            List of stop sequences
        """
        # Use the Coq tool's closing tag as stop sequence
        return [f"</{self.coq_tool.tag}>"]

    def get_initial_state(
        self, beam_size: int
    ) -> Tuple[List[ScriptTool], List[int]]:
        """
        Create the initial state for a proof search with multiple beams.

        Args:
            beam_size: Number of parallel paths to explore

        Returns:
            Tuple of (Coq tools, active indices)
        """
        # Create deep copies of the Coq tool for each beam
        coq_tools = [self.coq_tool.deepcopy() for _ in range(beam_size)]

        # Track which beams are active
        active_indices = list(range(beam_size))

        return coq_tools, self.coq_tool.tag  # active_indices
