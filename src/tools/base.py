from abc import ABC, abstractmethod
from typing import Any

class ToolError(Exception):
    def __init__(self, message):
        self.message = message

class BaseTool(ABC):
    """Abstract base class for all tools."""

    @property
    @abstractmethod
    def instruction(self) -> str:
        """Return the instructions on how to use the tool."""
        pass

    @property
    @abstractmethod
    def tag(self) -> str:
        """Return the XML tag name to use for this tool."""
        pass

    @abstractmethod
    def run(self, input_text: str) -> Any:
        """Execute the tool functionality."""
        pass
