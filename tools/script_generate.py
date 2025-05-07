import os
import json

from tqdm import tqdm
import torch

from tools.embedding_model import MxbaiEmbedding

embedding_json_path = 'dataset/embedding/json'
embedding_pt_path= 'dataset/embedding/pt'


model = MxbaiEmbedding()
for filename in os.listdir(embedding_json_path):
    export_path = os.path.join(embedding_pt_path, filename.replace('.json', '.pt'))
    filepath = os.path.join(embedding_json_path, filename)

    with open(filepath, 'r') as file:
        doc = json.load(file)
    for key, value in tqdm(doc.items()):
        embeddings = model.generate(value)
        doc[key] = {"embedding": embeddings, "docstring": value}
    torch.save(doc, export_path)
