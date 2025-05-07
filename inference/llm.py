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


class VLLM(LLM):
    """Implementation of LLM using VLLM's OpenAI-compatible API."""

    def __init__(
        self,
        api_url: str,
        model: str = "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B",  # not used!
        temperature: float = 0.1,
        top_p: float = 0.9,
        top_k: int = 40,
        max_tokens: int = 1024,
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
        payload = {
            "prompt": prompt,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "max_tokens": self.max_tokens,
        }
        len_prompt = len(prompt)

        if stop_sequences:
            payload["stop"] = stop_sequences

        response = requests.post(
            f"{self.api_url}/generate",
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
        )

        if response.status_code != 200:
            raise Exception(
                f"LLM API returned error: {response.status_code} - {response.text}"
            )
        if self.verbose:
            print(f"LLM API response: {response.json()["text"][0][len_prompt:]}")

        return response.json()["text"][0][len_prompt:]
