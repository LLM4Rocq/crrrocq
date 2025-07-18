from typing import List, Optional, Dict

import openai
from transformers import AutoTokenizer

from .base import BaseLLM

class OpenAIInstructLLM(BaseLLM):
    """Class for LLM providers compatible with OpenAI API."""

    def __init__(self, model_name: str="", generation_parameters: dict={}, base_url="http://127.0.0.1:30000/v1", api_key="None"):
        super().__init__()
        self.model_name = model_name
        self.generation_parameters = generation_parameters
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.client = openai.Client(base_url=base_url, api_key=api_key)
    
    def generate(
            self, messages: List[Dict[str, str]], **kwargs
    ) -> str:
        """Generate a completion using the LLM."""
        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            continue_final_message=True
        )
        response = self.client.completions.create(
            model=self.model_name,
            prompt=prompt,
            **self.generation_parameters,
            **kwargs
        )
        return response