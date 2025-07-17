import os
from typing import List, Tuple, Dict
from abc import ABC, abstractmethod
import copy
import hashlib

import torch
import faiss
from tqdm import tqdm

from ..models.base import BaseEmbedding



def string_to_filename(s):
    # Encode the string to bytes, then hash it
    h = hashlib.sha256(s.encode('utf-8')).hexdigest()
    return h

class CosimIndex(ABC):
    """Abstract base class for cosim search."""

    @abstractmethod
    def query(self, sentence: str, top_k=10) -> List[Tuple[float, str, str]]:
        """Query index
        return a list of score, key, label"""
        pass


class FaissIndex(CosimIndex):
    def __init__(
        self, model: BaseEmbedding, content: Dict = {}, cache_path: str="export/cache/", load_cache_index=True
    ):
        super().__init__()
        self.model = model
        self.all_embeddings = []
        self.all_fqn = []
        self.all_constants = []
        self.cache_path = os.path.join(cache_path, model.name())
        self.content = copy.deepcopy(content)

        os.makedirs(self.cache_path, exist_ok=True)
        self._compute_and_save_embedding()
        for qualid_name, element in self.content.items():
            embedding = element["embedding"]
            self.all_fqn.append(qualid_name)
            self.all_constants.append(element)
            self.all_embeddings.append(embedding)
        self.all_embeddings = torch.cat(self.all_embeddings, dim=0).to(torch.float32).numpy()
        d = self.all_embeddings.shape[1]
        faiss.normalize_L2(self.all_embeddings)
        
        cache_index_path = os.path.join(cache_path, f"index_{model.name()}")
        if load_cache_index and os.path.exists(cache_index_path):
            self.index = faiss.read_index(cache_index_path)
        else:
            self.index = faiss.IndexFlatIP(d)
            self.index.add(self.all_embeddings)
            faiss.write_index(self.index, cache_index_path)
        

    def _compute_and_save_embedding(self):
        to_do = []
        for qualid_name, element in self.content.items():
            filename = string_to_filename(qualid_name) + '.pt'
            export_path = os.path.join(self.cache_path, filename)
            if not os.path.exists(export_path):
                to_do.append((export_path, element, qualid_name))
            else:
                cache_element = torch.load(export_path)
                self.content[qualid_name]['embedding'] = cache_element['embedding']
        for export_path, element, qualid_name in tqdm(to_do):
            try:
                embedding = self.model.generate(element['docstring'])
                embedding = embedding.detach().clone().cpu()
                element['embedding'] = embedding
                torch.save({'embedding': embedding}, export_path)
            except Exception as e:
                del self.content[qualid_name]
                print(e)

    def query(self, query: str, top_k=10) -> List[Tuple[float, str, str]]:
        query_embedding = self.model.generate(query).detach().clone().cpu().to(torch.float32)
        distances, indices = self.index.search(query_embedding, top_k)

        result = []
        for i, idx in enumerate(indices[0]):
            element = copy.deepcopy(self.all_constants[idx])
            del element['embedding']
            result.append(
                (float(distances[0][i]), element, self.all_fqn[idx])
            )

        return result
