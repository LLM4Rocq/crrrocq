import hashlib

import torch
from torch import Tensor
import openai

from .base import BaseEmbedding


def string_to_filename(s):
    # Encode the string to bytes, then hash it
    h = hashlib.sha256(s.encode('utf-8')).hexdigest()
    return h

class OpenAIEmbedding(BaseEmbedding):
    """Wrapper around Qwen embedding models."""
    def __init__(self, model_name, base_url="http://127.0.0.1:30000/v1", api_key="None"):
        super().__init__()
        self.model_name = model_name
        self.client = openai.Client(base_url=base_url, api_key=api_key)
    
    def generate(self, text:str) -> Tensor:
        response = self.client.embeddings.create(
            model=self.model_name,
            input=text,
        )
        return torch.tensor(response.data[0].embedding).unsqueeze(0)

    def name(self) -> str:
        return f"openai_{string_to_filename(self.model_name)}"