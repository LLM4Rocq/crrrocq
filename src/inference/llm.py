import json
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union, Tuple, Callable
import requests
from dataclasses import dataclass
import concurrent.futures
import threading

from .llm_logger import LLMLogger
from .prompts import tactic_prompts

# ===============================================
# LLM Interface and Implementations
# ===============================================


class LLM(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate(self, prompt: str, stop_sequences: Optional[List[str]] = None) -> str:
        """Generate a completion using the LLM."""
        pass

    @abstractmethod
    def generate_batch(
        self, prompts: List[str], stop_sequences: Optional[List[str]] = None
    ) -> List[str]:
        """Generate completions for multiple prompts."""
        pass


class VLLM(LLM):
    """Implementation of LLM using VLLM's OpenAI-compatible API."""

    def __init__(
        self,
        api_url: str,
        model: str,
        temperature: float = 1,
        top_p: float = 0.9,
        top_k: int = 40,
        max_tokens: int = 16384,
        verbose: bool = True,
        log_dir: str = "bench16_logs",
        log_to_console: bool = False,
        session_name: str = None,
    ):
        self.api_url = api_url
        self.model = model
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k
        self.max_tokens = max_tokens
        self.verbose = verbose

        # Initialize the LLM logger with session name
        self.logger = LLMLogger(
            log_dir=log_dir,
            enabled=True,
            log_to_console=log_to_console or verbose,
            session_name=session_name,
        )

    def build_prompt(
        self, goals: str, coq_tag: str, context: str = "", goals_tag: str = "GOALS"
    ) -> str:
        """
        Build the initial prompt for the LLM.

        Args:
            theorem_code: The theorem code to prove
            coq_tag: The XML tag to use for Coq code

        Returns:
            The constructed prompt
        """
        return tactic_prompts.basic_prompt.format(
            coq_tag=coq_tag, goals_tag=goals_tag, goals=goals, context=context
        )

    def build_prompt_with_feedback(
        self,
        goals: str,
        coq_tag: str,
        response: str = "",
        # added_tactic: bool = False,
        success: bool = False,
        current_proof: str = "",
        previous_attempts: List[str] = None,
        context: str = "",
        goals_tag: str = "GOALS",
    ) -> str:
        """
        Build a prompt that includes feedback from previous proof attempts.

        Args:
            goals: The current Coq goals to prove
            coq_tag: The XML tag to use for Coq code
            previous_attempts: List of dictionaries containing previous attempts and results
                            Each dict should have 'script', 'response', 'success' keys
            context: Additional context to include in the prompt
            goals_tag: The XML tag to use for goals
            max_attempts: Maximum number of previous attempts to include in the prompt

        Returns:
            The constructed prompt with feedback from previous attempts
        """

        if success:
            prompt = tactic_prompts.prompt_progress.format(
                response=response,
                current_proof=current_proof,
                previous_attempts=previous_attempts,
                goals_tag=goals_tag,
                goals=goals,
            )
        else:
            prompt = tactic_prompts.prompt_failed.format(
                response=response,
                previous_attempts=previous_attempts,
                goals_tag=goals_tag,
                goals=goals,
            )

        return prompt

    def generate(
        self,
        prompt: str,
        stop_sequences: Optional[List[str]] = None,
        session_name: str = None,
    ) -> str:
        """Generate a completion using VLLM's OpenAI-compatible API."""
        responses = self.generate_batch([prompt], stop_sequences)
        return responses[0] if responses else ""

    def generate_batch(
        self,
        prompts: List[str],
        stop_sequences: Optional[List[str]] = None,
        session_name: str = None,
    ) -> List[str]:
        """
        Generate completions for multiple prompts.

        Args:
            prompts: List of prompts to generate completions for
            stop_sequences: Optional list of stop sequences

        Returns:
            List of generated completions corresponding to each prompt
        """
        if not prompts:
            return []

        payload = {
            "model": self.model,
            "prompt": prompts,
            "temperature": self.temperature,
            # "top_p": self.top_p,
            # "top_k": self.top_k,
            "max_tokens": self.max_tokens,
            # "include_stop_str_in_output": True, not working in sglang
            "stream": False,
        }

        # Add optional parameters if specified
        if stop_sequences:
            payload["stop"] = stop_sequences

        try:
            response = requests.post(
                f"{self.api_url}/v1/completions",
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload),
            )

            if response.status_code != 200:
                raise Exception(
                    f"LLM API returned error: {response.status_code} - {response.text}"
                )

            data = response.json()

            # print(f"LLM API response: {data}")

            # Extract the completions from the response
            llm_responses = [
                choice["text"]
                + (choice["matched_stop"] if choice["matched_stop"] != 151645 else "")
                for choice in data["choices"]
            ]
            # llm_responses = [choice["text"] for choice in data["choices"]]

            # Log the interaction
            metadata = {
                "model": self.model,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "stop_sequences": stop_sequences,
            }

            # Log the batch interaction
            self.logger.log_batch_interaction(
                prompts=prompts,
                responses=llm_responses,
                metadata=metadata,
                prefix=self.model.split("/")[-1],  # Use model name as prefix
            )

            return llm_responses

        except Exception as e:
            print(f"Error in generate_batch: {e}")
            # Return empty strings in case of error
            return [""] * len(prompts)

    def finalize_session(self) -> None:
        """Finalize the logging session."""
        self.logger.finalize_session()

    def get_session_log_path(self) -> str:
        """Get the path to the current session log file."""
        return self.logger.get_session_path()


class ThreadLocalVLLM:
    """
    Thread-safe wrapper for VLLM that creates one instance per thread.
    Perfect for scenarios with multiple sequential LLM calls within each thread.
    """

    def __init__(self, **vllm_config):
        """
        Initialize the thread-local VLLM wrapper.

        Args:
            **vllm_config: Configuration parameters to pass to VLLM constructor
        """
        self.vllm_config = vllm_config
        self.local = threading.local()
        self._instance_count = 0
        self._lock = threading.Lock()

    def _get_instance(self, session_name: str = None) -> VLLM:
        """Get or create a VLLM instance for the current thread."""
        if not hasattr(self.local, "vllm"):
            with self._lock:
                self._instance_count += 1
                instance_id = self._instance_count

            thread_name = threading.current_thread().name
            print(f"Creating VLLM instance #{instance_id} for thread {thread_name}")

            # Create without session name initially
            self.local.vllm = VLLM(**self.vllm_config)
            self.local.instance_id = instance_id

        # If session name is provided, create a new logger for this session
        if session_name and hasattr(self.local, "vllm"):
            llm = self.local.vllm
            # Create a new logger with the specific session name
            from .llm_logger import LLMLogger

            llm.logger = LLMLogger(
                log_dir="bench16_logs",
                enabled=True,
                log_to_console=True,
                session_name=session_name,
            )

        return self.local.vllm

    def generate(
        self,
        prompt: str,
        stop_sequences: Optional[List[str]] = None,
        session_name: str = None,
    ) -> str:
        """Generate a completion using the thread-local VLLM instance."""
        llm = self._get_instance(session_name)
        return llm.generate(prompt, stop_sequences)

    def generate_batch(
        self,
        prompts: List[str],
        stop_sequences: Optional[List[str]] = None,
        session_name: str = None,
    ) -> List[str]:
        """Generate completions for multiple prompts using the thread-local VLLM instance."""
        llm = self._get_instance(session_name)
        return llm.generate_batch(prompts, stop_sequences)

    def build_prompt(
        self,
        goals: str,
        coq_tag: str,
        context: str = "",
        goals_tag: str = "GOALS",
        session_name: str = None,
    ) -> str:
        """Build the initial prompt for the LLM."""
        llm = self._get_instance(session_name)
        return llm.build_prompt(goals, coq_tag, context, goals_tag)

    def build_prompt_with_feedback(
        self,
        goals: str,
        coq_tag: str,
        response: str = "",
        success: bool = False,
        current_proof: str = "",
        previous_attempts: List[str] = None,
        context: str = "",
        goals_tag: str = "GOALS",
        session_name: str = None,
    ) -> str:
        """Build a prompt that includes feedback from previous proof attempts."""
        llm = self._get_instance(session_name)
        return llm.build_prompt_with_feedback(
            goals,
            coq_tag,
            response,
            success,
            current_proof,
            previous_attempts,
            context,
            goals_tag,
        )

    @property
    def instance_count(self) -> int:
        """Get the total number of VLLM instances created."""
        return self._instance_count
