from tools.embedding_model import MxbaiEmbedding
from tools.cosim_index import FaissIndex

embedding_pt_path= 'dataset/embedding/pt'

model = MxbaiEmbedding()
index = FaissIndex(model, embedding_pt_path)

while True:
    query = input('Query:')
    result = index.query(query)

    for score, key, docstring in result:
        print(score, key)
        print(docstring)
        print()