import os
import sys

from search.embedding_model import MxbaiEmbedding, GteQwenEmbedding
from search.cosim_index import FaissIndex

embedding_path= 'dataset/embedding/pt'

model = GteQwenEmbedding()
index = FaissIndex(model, embedding_path=embedding_path)

while True:
    query = input('Query:')
    os.system('clear')
    result = index.query(query)

    for score, key, docstring in result:
        print(score, key)
        print(docstring)
        print()