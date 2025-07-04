from abc import ABC, abstractmethod
from typing import List, Optional

class BaseLLM(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate a completion using the LLM."""
        pass