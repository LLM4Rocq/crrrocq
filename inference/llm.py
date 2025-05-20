import json
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union, Tuple
import requests
from dataclasses import dataclass
from llm_logger import LLMLogger
from prompts import tactic_prompts

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
        temperature: float = 1.0,
        top_p: float = 0.9,
        top_k: int = 40,
        max_tokens: int = 16384,
        verbose: bool = False,
        log_dir: str = "llm_logs",
        log_to_console: bool = False,
    ):
        self.api_url = api_url
        self.model = model
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k
        self.max_tokens = max_tokens
        self.verbose = verbose

        # Initialize the LLM logger
        self.logger = LLMLogger(
            log_dir=log_dir, enabled=True, log_to_console=log_to_console or verbose
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
        # Start with the basic prompt
        prompt = self.build_prompt(
            goals=goals, coq_tag=coq_tag, context=context, goals_tag=goals_tag
        )

        # If there are no previous attempts, return the basic prompt
        if not previous_attempts or len(previous_attempts) == 0:
            return prompt

        # Add a section about previous attempts
        prompt += f"\n\nHere are some previous attempts to solve this problem:\n {previous_attempts}"

        # Add a reminder about the current goals
        prompt += f"\nNow, let's try again. Here are the current goals:\n<{goals_tag}>\n{goals}\n</{goals_tag}>\n"
        prompt += (
            "Please analyze the previous attempts and propose a new proof strategy."
        )

        return prompt

    def generate(self, prompt: str, stop_sequences: Optional[List[str]] = None) -> str:
        """Generate a completion using VLLM's OpenAI-compatible API."""
        responses = self.generate_batch([prompt], stop_sequences)
        return responses[0] if responses else ""

    def generate_batch(
        self, prompts: List[str], stop_sequences: Optional[List[str]] = None
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
            "include_stop_str_in_output": True,
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

            # if self.verbose:
            #    print(f"LLM API response: {data}")

            # Extract the completions from the response
            llm_responses = [choice["text"] for choice in data["choices"]]

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
