from typing import Dict
from abc import ABC, abstractmethod

import torch
from torch import Tensor
import numpy as np

from transformers import AutoModel, AutoTokenizer

def transform_query(query: str) -> str:
    """ For retrieval, add the prompt for query (not for documents).
    """
    return f'Represent this sentence for searching relevant passages: {query}'

def pooling(outputs: torch.Tensor, inputs: Dict,  strategy: str = 'cls') -> np.ndarray:
    if strategy == 'cls':
        outputs = outputs[:, 0]
    elif strategy == 'mean':
        outputs = torch.sum(
            outputs * inputs["attention_mask"][:, :, None], dim=1) / torch.sum(inputs["attention_mask"], dim=1, keepdim=True)
    else:
        raise NotImplementedError
    return outputs.detach()

class EmbeddingModel(ABC):
    """Abstract base class for embedding model."""

    @abstractmethod
    def generate(self, sentence:str, query=False) -> Tensor:
        """Generate an embedding"""
        pass

class MxbaiEmbedding(EmbeddingModel):

    def __init__(self):
        super().__init__()
        model_id = 'mixedbread-ai/mxbai-embed-large-v1'
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        self.model = AutoModel.from_pretrained(model_id)

    def generate(self, sentence:str, query=False) -> Tensor:
        if query:
            sentence = transform_query(sentence)
        inputs = self.tokenizer(sentence, padding=True, return_tensors='pt', truncation=True)
        outputs = self.model(**inputs).last_hidden_state
        embeddings = pooling(outputs, inputs, 'cls')
        return embeddings
