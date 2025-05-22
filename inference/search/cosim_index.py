import os
import json
from typing import List, Tuple
from abc import ABC, abstractmethod

import torch
import faiss
from tqdm import tqdm

from search.embedding_model import EmbeddingModel

class CosimIndex(ABC):
    """Abstract base class for cosim search."""

    @abstractmethod
    def query(self, sentence:str, top_k=10) -> List[Tuple[float, str, str]]:
        """Query index
        return a list of score, key, label"""
        pass

class FaissIndex(CosimIndex):
    def __init__(self, model:EmbeddingModel, text_path:str=None, embedding_path:str=None):
        super().__init__()
        self.model = model
        self.all_keys = []
        self.all_labels = []
        self.all_embeddings = []

        if text_path:
            self._compute_embedding(text_path, embedding_path)
        for filename in os.listdir(embedding_path):
            if not filename.endswith('.pt'):
                continue
            filepath = os.path.join(embedding_path, filename)
            embeddings = torch.load(filepath)
            for key, entry in embeddings.items():
                label = entry['docstring']
                embedding = entry['embedding']
                self.all_keys.append(key)
                self.all_labels.append(label)
                self.all_embeddings.append(embedding)

        self.all_embeddings = torch.cat(self.all_embeddings, dim=0)
        d = self.all_embeddings.shape[1]

        self.index = faiss.IndexFlatIP(d)
        self.index.add(self.all_embeddings)
    
    def _compute_embedding(self, text_path: str, embedding_path: str):
        for filename in tqdm(os.listdir(text_path)):
            export_path = os.path.join(embedding_path, filename.replace('.json', '.pt'))
            filepath = os.path.join(text_path, filename)

            with open(filepath, 'r') as file:
                doc = json.load(file)
            for key, dict in doc.items():
                embeddings = self.model.generate(dict['docstring'])
                doc[key] = {"embedding": embeddings.detach().clone().cpu(), **dict}
            torch.save(doc, export_path)

    def query(self, query:str, top_k=10) -> List[Tuple[float, str, str]]:
        query_embedding = self.model.generate(query, query=True)
        distances, indices = self.index.search(query_embedding, top_k)

        result = []
        for i, idx in enumerate(indices[0]):
            result.append((distances[0][i], self.all_keys[idx], self.all_labels[idx]))
        
        return result