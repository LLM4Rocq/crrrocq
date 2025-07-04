import json

import yaml
from flask import Flask, request, jsonify

from src.embedding.index.cosim_index import FaissIndex
from src.embedding.models.openai import OpenAIEmbedding

app = Flask(__name__)

with open('src/servers/retrieval/config.yaml', 'r') as file:
    config = yaml.safe_load(file)

with open(config['docstrings_path'], 'r') as file:
    dictionary = json.load(file)

embedding = OpenAIEmbedding(config['model_name'])
index = FaissIndex(embedding, content=dictionary, cache_path=config['cache_path'])

@app.route('/query', methods=['POST'])
def query():
    try:
        data = request.get_json()
        query = data['query']
        top_k = data['top_k']

        output = index.query(query, top_k=top_k)
        return jsonify(output), 200
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)