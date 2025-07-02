import os
from typing import List, Tuple, Dict
from abc import ABC, abstractmethod
import copy
import hashlib

import torch
import faiss
from tqdm import tqdm

from src.embedding_models.base import BaseModel



def string_to_filename(s):
    # Encode the string to bytes, then hash it
    h = hashlib.sha256(s.encode('utf-8')).hexdigest()
    return h

def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

class CosimIndex(ABC):
    """Abstract base class for cosim search."""

    @abstractmethod
    def query(self, sentence: str, top_k=10) -> List[Tuple[float, str, str]]:
        """Query index
        return a list of score, key, label"""
        pass


class FaissIndex(CosimIndex):
    def __init__(
        self, model: BaseModel, content: Dict = None, cache_path: str="export/cache/", batch_size=1, load_cache_index=True
    ):
        super().__init__()
        self.model = model
        self.all_embeddings = []
        self.all_fqn = []
        self.all_constants = []
        self.cache_path = os.path.join(cache_path, model.name())
        self.content = copy.deepcopy(content)

        os.makedirs(self.cache_path, exist_ok=True)
        self._compute_and_save_embedding(batch_size=batch_size)


        for qualid_name, element in self.content.items():
            embedding = element["embedding"]
            self.all_fqn.append(qualid_name)
            self.all_constants.append(element)
            self.all_embeddings.append(embedding.unsqueeze(0))

        self.all_embeddings = torch.cat(self.all_embeddings, dim=0).to(torch.float32).numpy()
        d = self.all_embeddings.shape[1]
        faiss.normalize_L2(self.all_embeddings)
        
        cache_index_path = os.path.join(cache_path, "index")
        if load_cache_index and os.path.exists(cache_index_path):
            self.index = faiss.read_index(cache_index_path)
        else:
            self.index = faiss.IndexFlatIP(d)
            self.index.add(self.all_embeddings)
            faiss.write_index(self.index, cache_index_path)
        

    def _compute_and_save_embedding(self, batch_size=1):
        to_do = []
        for qualid_name, element in self.content.items():
            filename = string_to_filename(qualid_name) + '.pt'
            export_path = os.path.join(self.cache_path, filename)
            if not os.path.exists(export_path):
                to_do.append((export_path, element))
            else:
                cache_element = torch.load(export_path)
                element['embedding'] = cache_element['embedding']
        to_do_chunk = list(chunks(to_do, batch_size))
        for batch in tqdm(to_do_chunk):
            docstring_lists = [e['docstring'] for (_, e) in batch]
            embeddings = self.model.generate(docstring_lists)
            for (export_path, element), embedding in zip(batch, embeddings):
                embedding = embedding.detach().clone().cpu()
                element['embedding'] = embedding
                torch.save({'embedding': embedding}, export_path)

    def query(self, query: str, top_k=10) -> List[Tuple[float, str, str]]:
        query_embedding = self.model.generate(query, query=True).detach().clone().cpu().to(torch.float32)
        distances, indices = self.index.search(query_embedding, top_k)

        result = []
        for i, idx in enumerate(indices[0]):
            element = copy.deepcopy(self.all_constants[idx])
            del element['embedding']
            result.append(
                (float(distances[0][i]), element, self.all_fqn[idx])
            )

        return result
