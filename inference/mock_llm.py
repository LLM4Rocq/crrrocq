from llm import LLM
from typing import List, Optional


class MockVLLM(LLM):
    """A mock implementation of the VLLM class that allows manual control."""

    def __init__(self):
        """Initialize the mock VLLM."""
        self.prompt_history = []

    def generate(self, prompt: str, stop_sequences: Optional[List[str]] = None) -> str:
        """
        Instead of calling an external API, this method saves the prompt
        and allows the user to manually enter a response.

        Args:
            prompt: The prompt to generate from
            stop_sequences: List of sequences that stop generation

        Returns:
            The user-provided response
        """
        # Save the prompt for reference
        self.prompt_history.append(prompt)

        # Print the prompt for the user to see
        print("\n" + "=" * 80)
        print("PROMPT RECEIVED:")
        print("=" * 80)
        print(prompt)
        print("=" * 80)

        # Get the user's response
        print("\nEnter your response (type 'END' on a new line to finish):")
        lines = []
        while True:
            line = input()
            if line.strip() == "END":
                break
            lines.append(line)

        # Combine the lines into a response
        response = "\n".join(lines)

        # Handle stop sequences if provided
        if stop_sequences:
            for seq in stop_sequences:
                if seq in response:
                    # Truncate the response at the stop sequence, but include the stop sequence
                    parts = response.split(seq, 1)
                    response = parts[0] + seq
                    break

        return response
