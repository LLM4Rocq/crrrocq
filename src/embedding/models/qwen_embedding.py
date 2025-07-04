import os

import torch
from torch import Tensor
import torch.nn.functional as F

from transformers import AutoModel, AutoTokenizer

from .base import BaseEmbedding

def last_token_pool(last_hidden_states: Tensor,
                 attention_mask: Tensor) -> Tensor:
    """Return the embedding of the last non padding token."""
    left_padding = (attention_mask[:, -1].sum() == attention_mask.shape[0])
    if left_padding:
        return last_hidden_states[:, -1]
    else:
        sequence_lengths = attention_mask.sum(dim=1) - 1
        batch_size = last_hidden_states.shape[0]
        return last_hidden_states[torch.arange(batch_size, device=last_hidden_states.device), sequence_lengths]


def get_detailed_instruct(task_description: str, query: str) -> str:
    """Format a retrieval instruction for the model."""
    return f'Instruct: {task_description}\nQuery: {query}'

class Qwen3Embedding(BaseEmbedding):
    """Wrapper around Qwen embedding models."""
    def __init__(self, device:str, size: str="0.6B", cache_dir="/lustre/fsn1/projects/rech/tdm/commun/hf_home/tokenizers"):
        super().__init__()
        assert size in ['0.6B', '4B', '8B']
        model_id = 'Qwen/Qwen3-Embedding-' + size
        self.device = device
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True, cache_dir=os.path.join(cache_dir, model_id))
        self.model = AutoModel.from_pretrained(model_id, trust_remote_code=True).to(device, dtype=torch.float32)
        self.prompt_query = 'Given a natural language query, retrieve formal Coq statements whose docstrings best match the intent of the query.'
        
    def generate(self, sentence:str, query=False) -> Tensor:
        if query:
            input_text = get_detailed_instruct(self.prompt_query, sentence)
        else:
            input_text = sentence
        
        batch_dict = self.tokenizer(input_text, padding=True, truncation=True, return_tensors='pt').to(self.device)
        outputs = self.model(**batch_dict)
        embeddings = last_token_pool(outputs.last_hidden_state, batch_dict['attention_mask'])
        embeddings = F.normalize(embeddings, p=2, dim=1) 
        return embeddings

    def name(self) -> str:
        return "qwen_embedding_base"

class Qwen3Embedding600m(Qwen3Embedding):
    def __init__(self, device):
        super().__init__(device, "0.6B")
    
    def name(self) -> str:
        return "qwen_embedding_600m"

class Qwen3Embedding4b(Qwen3Embedding):
    def __init__(self, device):
        super().__init__(device, "4B")
    
    def name(self) -> str:
        return "qwen_embedding_4b"

class Qwen3Embedding8b(Qwen3Embedding):
    def __init__(self, device):
        super().__init__(device, "8B")
    
    def name(self) -> str:
        return "qwen_embedding_8b"