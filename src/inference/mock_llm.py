from typing import List, Optional

from .llm import LLM

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
        # Use the batch version for consistency
        responses = self.generate_batch([prompt], stop_sequences)
        return responses[0] if responses else ""

    def generate_batch(
        self, prompts: List[str], stop_sequences: Optional[List[str]] = None
    ) -> List[str]:
        """
        Generate completions for multiple prompts through manual user input.

        Args:
            prompts: List of prompts to generate completions for
            stop_sequences: Optional list of stop sequences

        Returns:
            List of user-provided responses corresponding to each prompt
        """
        responses = []

        for i, prompt in enumerate(prompts):
            # Save the prompt for reference
            self.prompt_history.append(prompt)

            # Print the prompt for the user to see
            print("\n" + "=" * 80)
            print(f"PROMPT #{i+1} OF {len(prompts)}:")
            print("=" * 80)
            print(prompt)
            print("=" * 80)

            # Get the user's response
            print(
                f"\nEnter your response for prompt #{i+1} (type 'END' on a new line to finish):"
            )
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

            responses.append(response)

        return responses
