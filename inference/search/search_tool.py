from typing import List

from tools import Tool
from search.cosim_index import FaissIndex
from search.embedding_model import GteQwenEmbedding, MxbaiEmbedding

class SearchTool(Tool):
    """Tool for searching relevant information."""

    def __init__(self, embedding_path):
        super().__init__()
        self.model = GteQwenEmbedding()
        self.index = FaissIndex(self.model, embedding_path=embedding_path)

    @property
    def name(self) -> str:
        return "search"

    @property
    def description(self) -> str:
        return "Search for relevant mathematical theorems, definitions, or proofs."

    @property
    def tag(self) -> str:
        return "SEARCH"

    def run(self, query:str, top_k:int=5) -> List[str]:
        """
        Execute a search and return results.

        Note: This is a placeholder. Implement actual search functionality here.
        """
        result = self.index.query(query, top_k=top_k)
        result = [fullname for _,_, fullname in result]
        # This would be replaced with actual search functionality
        return result