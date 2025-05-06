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
        model: str = "mistral-7b",
        temperature: float = 0.1,
        top_p: float = 0.9,
        top_k: int = 40,
        max_tokens: int = 1024,
    ):
        self.api_url = api_url
        self.model = model
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k
        self.max_tokens = max_tokens

    def generate(self, prompt: str, stop_sequences: Optional[List[str]] = None) -> str:
        """Generate a completion using VLLM's OpenAI-compatible API."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "max_tokens": self.max_tokens,
        }

        if stop_sequences:
            payload["stop"] = stop_sequences

        response = requests.post(
            f"{self.api_url}/v1/completions",
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
        )

        if response.status_code != 200:
            raise Exception(
                f"LLM API returned error: {response.status_code} - {response.text}"
            )

        return response.json()["choices"][0]["text"]
