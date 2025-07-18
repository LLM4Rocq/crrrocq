import os
import json
import logging
from datetime import datetime
from typing import Optional


class LLMLogger:
    """
    Simple logger specifically for LLM prompts and responses.

    This logger accumulates all interactions in a single JSON file for a proof session.
    """

    def __init__(
        self,
        log_dir: str = "llm_logs",
        enabled: bool = True,
        log_to_console: bool = False,
        session_name: str = None,
    ):
        """
        Initialize the LLM logger.

        Args:
            log_dir: Directory to store log files
            enabled: Whether logging is enabled
            log_to_console: Whether to also print logs to console
            session_name: Name for this proof session (used in filename)
        """
        self.log_dir = log_dir
        self.enabled = enabled
        self.log_to_console = log_to_console
        
        # Create session-specific filename
        if session_name:
            self.log_filename = f"proof_session_{session_name}.json"
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.log_filename = f"proof_session_{timestamp}.json"
            
        self.log_path = os.path.join(log_dir, self.log_filename)
        
        # Initialize the session log data
        self.session_data = {
            "session_start": datetime.now().isoformat(),
            "session_name": session_name or "unnamed",
            "interactions": []
        }

        # Create log directory if it doesn't exist
        if enabled:
            os.makedirs(log_dir, exist_ok=True)
            # Initialize the log file
            self._write_session_data()

    def _write_session_data(self) -> None:
        """Write the current session data to the log file."""
        if not self.enabled:
            return
            
        with open(self.log_path, "w") as f:
            json.dump(self.session_data, f, indent=2)

    def log_interaction(
        self,
        prompt: str,
        response: str,
        metadata: Optional[dict] = None,
        prefix: str = "",
    ) -> None:
        """
        Log a single LLM interaction to the session file.

        Args:
            prompt: The prompt sent to the LLM
            response: The response from the LLM
            metadata: Optional metadata to include in the log
            prefix: Optional prefix (kept for compatibility but not used)
        """
        if not self.enabled:
            return

        # Create a timestamp
        timestamp = datetime.now().isoformat()

        # Create interaction data
        interaction_data = {
            "timestamp": timestamp,
            "prompt": prompt,
            "response": response,
            "interaction_type": "single"
        }

        # Add metadata if provided
        if metadata:
            interaction_data["metadata"] = metadata

        # Keep only the last interaction
        self.session_data["interactions"] = [interaction_data]
        
        # Write updated session data to file
        self._write_session_data()

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
        Log a batch of LLM interactions to the session file.

        Args:
            prompts: The prompts sent to the LLM
            responses: The responses from the LLM
            metadata: Optional metadata to include in the log
            prefix: Optional prefix (kept for compatibility but not used)
        """
        if not self.enabled:
            return

        # Create a timestamp
        timestamp = datetime.now().isoformat()

        # Create batch interaction data
        batch_interaction_data = {
            "timestamp": timestamp,
            "interaction_type": "batch",
            "batch_size": len(prompts),
            "interactions": [
                {"prompt": p, "response": r} for p, r in zip(prompts, responses)
            ],
        }

        # Add metadata if provided
        if metadata:
            batch_interaction_data["metadata"] = metadata

        # Keep only the last interaction
        self.session_data["interactions"] = [batch_interaction_data]
        
        # Write updated session data to file
        self._write_session_data()

        # Print to console if enabled
        if self.log_to_console:
            print(f"\n=== LLM Batch Interaction at {timestamp} ===")
            print(f"Number of interactions: {len(prompts)}")
            print("=" * 50)

    def finalize_session(self) -> None:
        """
        Finalize the session by adding end timestamp and final write.
        """
        if not self.enabled:
            return
            
        self.session_data["session_end"] = datetime.now().isoformat()
        self.session_data["total_interactions"] = len(self.session_data["interactions"])
        self._write_session_data()

    def get_session_path(self) -> str:
        """
        Get the path to the current session log file.
        
        Returns:
            Path to the session log file
        """
        return self.log_path
