import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search.embedding_model import GteQwenEmbedding, MxbaiEmbedding
from search.cosim_index import FaissIndex

text_path = 'dataset/embedding/json'
embedding_path= 'dataset/embedding/pt'

model = GteQwenEmbedding()
index = FaissIndex(model, text_path=text_path, embedding_path=embedding_path)
