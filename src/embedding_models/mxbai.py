from typing import Dict

import torch
from torch import Tensor
import numpy as np
import torch.nn.functional as F

from transformers import AutoModel, AutoTokenizer

from src.models.base import BaseModel

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

class MxbaiEmbedding(BaseModel):

    def __init__(self, device):
        super().__init__()
        self.device = device
        model_id = 'mixedbread-ai/mxbai-embed-large-v1'
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        self.model = AutoModel.from_pretrained(model_id).to(device, dtype=torch.bfloat16)

    def generate(self, sentence:str, query=False) -> Tensor:
        if query:
            sentence = transform_query(sentence)
        inputs = self.tokenizer(sentence, padding=True, return_tensors='pt', truncation=True).to(self.device)
        outputs = self.model(**inputs).last_hidden_state
        embeddings = pooling(outputs, inputs, 'cls')
        return F.normalize(embeddings, p=2, dim=1) 

    def name(self) -> str:
        return "mxbai"