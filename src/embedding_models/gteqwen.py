import torch
from torch import Tensor
import torch.nn.functional as F

from transformers import AutoModel, AutoTokenizer

from src.models.base import BaseModel

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

class GteQwenEmbedding(BaseModel):
    def __init__(self, device:str):
        super().__init__()
        model_id = 'Alibaba-NLP/gte-Qwen2-7B-instruct'
        self.device = device
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        self.model = AutoModel.from_pretrained(model_id, trust_remote_code=True).to(device, dtype=torch.bfloat16)
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
        return "gte_qwen"