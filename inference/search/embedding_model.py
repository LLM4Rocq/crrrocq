from typing import Dict
from abc import ABC, abstractmethod

import torch
from torch import Tensor
import numpy as np
import torch.nn.functional as F

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

def last_token_pool(last_hidden_states: Tensor,
                 attention_mask: Tensor) -> Tensor:
    left_padding = (attention_mask[:, -1].sum() == attention_mask.shape[0])
    if left_padding:
        return last_hidden_states[:, -1]
    else:
        sequence_lengths = attention_mask.sum(dim=1) - 1
        batch_size = last_hidden_states.shape[0]
        return last_hidden_states[torch.arange(batch_size, device=last_hidden_states.device), sequence_lengths]


def get_detailed_instruct(task_description: str, query: str) -> str:
    return f'Instruct: {task_description}\nQuery: {query}'

class GteQwenEmbedding(EmbeddingModel):
    def __init__(self):
        super().__init__()
        model_id = 'Alibaba-NLP/gte-Qwen2-7B-instruct'
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        self.model = AutoModel.from_pretrained(model_id, trust_remote_code=True)
        self.prompt_query = 'Given a natural language query, retrieve formal Coq statements whose docstrings best match the intent of the query.'
    
    def generate(self, sentence:str, query=False) -> Tensor:
        if query:
            input_text = get_detailed_instruct(self.prompt_query, sentence)
        else:
            input_text = sentence
        
        batch_dict = self.tokenizer(input_text, padding=True, truncation=True, return_tensors='pt')
        outputs = self.model(**batch_dict)
        embeddings = last_token_pool(outputs.last_hidden_state, batch_dict['attention_mask'])
        embeddings = F.normalize(embeddings, p=2, dim=1) 
        return embeddings
