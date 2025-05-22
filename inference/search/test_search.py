import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from search.search_tool import SearchTool

def test_search(embedding_path):
    st = SearchTool(embedding_path)
    print(st.run(query="Hello"))

test_search("dataset/embedding/pt")