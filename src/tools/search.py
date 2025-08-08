from src.servers.retrieval.client import RetrievalClient, ClientError

from .base import BaseTool, ToolError

class SearchTool(BaseTool):
    """Tool for searching relevant information."""

    def __init__(self, base_url, state=None):
        super().__init__()
        self.client = RetrievalClient(base_url)
        self.state = state

    @property
    def instruction(self) -> str:
        return """### 🔍 Search Block  
**Purpose**: Discover relevant theorems and lemmas
- Query the theorem database with natural language descriptions
- Find existing results that support your proof strategy
- Identify patterns, equivalences, and useful properties
- **Best Practice**: Be specific in your search queries
"""

    @property
    def tag(self) -> str:
        return "search"

    def run(self, query: str, top_k=10, source="", **kwargs) -> str:
        """
        Execute a search and return results.

        Note: This is a placeholder. Implement actual search functionality here.
        """
        try:
            search_result = self.client.query(query, top_k=top_k, source=source)
            output = ""
            # TODO: retrain with clean format
            for k, (_, element, _) in enumerate(search_result, start=1):
                fullname, docstring = element['fullname'], element['docstring']
                output += f"{k}. {fullname}\n{docstring}\n\n"
            return output
        except ClientError as e:
            raise ToolError(e.message) from e
