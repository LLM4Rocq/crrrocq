import os
import json
import logging
from datetime import datetime
from typing import Optional


class LLMLogger:
    """
    Simple logger specifically for LLM prompts and responses.

    This logger saves each interaction in a separate JSON file for easy analysis.
    """

    def __init__(
        self,
        log_dir: str = "llm_logs",
        enabled: bool = True,
        log_to_console: bool = False,
    ):
        """
        Initialize the LLM logger.

        Args:
            log_dir: Directory to store log files
            enabled: Whether logging is enabled
            log_to_console: Whether to also print logs to console
        """
        self.log_dir = log_dir
        self.enabled = enabled
        self.log_to_console = log_to_console

        # Create log directory if it doesn't exist
        if enabled:
            os.makedirs(log_dir, exist_ok=True)

    def log_interaction(
        self,
        prompt: str,
        response: str,
        metadata: Optional[dict] = None,
        prefix: str = "",
    ) -> None:
        """
        Log a single LLM interaction.

        Args:
            prompt: The prompt sent to the LLM
            response: The response from the LLM
            metadata: Optional metadata to include in the log
            prefix: Optional prefix for the log filename
        """
        if not self.enabled:
            return

        # Create a timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

        # Create log data
        log_data = {"timestamp": timestamp, "prompt": prompt, "response": response}

        # Add metadata if provided
        if metadata:
            log_data["metadata"] = metadata

        # Create log filename with optional prefix
        filename = f"{prefix}_" if prefix else ""
        filename += f"llm_interaction_{timestamp}.json"

        # Write to log file
        log_path = os.path.join(self.log_dir, filename)
        with open(log_path, "w") as f:
            json.dump(log_data, f, indent=2)

        # Print to console if enabled
        if self.log_to_console:
            print(f"\n=== LLM Interaction at {timestamp} ===")
            print(f"Prompt: {prompt[:200]}...")
            print(f"Response: {response[:200]}...")
            print("=" * 50)

    def log_batch_interaction(
        self,
        prompts: list[str],
        responses: list[str],
        metadata: Optional[dict] = None,
        prefix: str = "",
    ) -> None:
        """
        Log a batch of LLM interactions.

        Args:
            prompts: The prompts sent to the LLM
            responses: The responses from the LLM
            metadata: Optional metadata to include in the log
            prefix: Optional prefix for the log filename
        """
        if not self.enabled:
            return

        # Create a timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

        # Create log data
        log_data = {
            "timestamp": timestamp,
            "interactions": [
                {"prompt": p, "response": r} for p, r in zip(prompts, responses)
            ],
        }

        # Add metadata if provided
        if metadata:
            log_data["metadata"] = metadata

        # Create log filename with optional prefix
        filename = f"{prefix}_" if prefix else ""
        filename += f"llm_batch_interaction_{timestamp}.json"

        # Write to log file
        log_path = os.path.join(self.log_dir, filename)
        with open(log_path, "w") as f:
            json.dump(log_data, f, indent=2)

        # Print to console if enabled
        if self.log_to_console:
            print(f"\n=== LLM Batch Interaction at {timestamp} ===")
            print(f"Number of interactions: {len(prompts)}")
            print("=" * 50)
