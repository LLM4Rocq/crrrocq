import json
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union, Tuple
import requests
from dataclasses import dataclass

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
        max_tokens: int = 2048,
        verbose: bool = False,
    ):
        self.api_url = api_url
        self.model = model
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k
        self.max_tokens = max_tokens
        self.verbose = verbose

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

            if self.verbose:
                print(f"LLM API response: {data}")

            # Extract the completions from the response
            llm_responses = [choice["text"] for choice in data["choices"]]

            return llm_responses

        except Exception as e:
            print(f"Error in generate_batch: {e}")
            # Return empty strings in case of error
            return [""] * len(prompts)
