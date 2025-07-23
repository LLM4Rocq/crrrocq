import json
import time
import os

import yaml
from flask import Flask, request, jsonify

from src.embedding.index.cosim_index import FaissIndex
from src.embedding.models.openai import OpenAIEmbedding

app = Flask(__name__)

with open('config/server/retrieval/config.yaml', 'r') as file:
    config = yaml.safe_load(file)

with open(config['docstrings_path'], 'r') as file:
    dictionary = json.load(file)

while not os.path.exists(os.environ['EMBED_IP_PATH']):
    time.sleep(20)

with open(os.environ['EMBED_IP_PATH'], 'r') as file:
    ip = file.read().strip()
    base_url = f"http://{ip}/v1"

embedding = OpenAIEmbedding(config['model_name'], base_url=base_url)
index = FaissIndex(embedding, content=dictionary, cache_path=config['cache_path'])
index_is_loaded = True

@app.route('/health', methods=['GET'])
def health():
    if index_is_loaded:
        return "OK", 200
    else:
        return "Index not loaded", 500

@app.route('/query', methods=['POST'])
def query():
    try:
        data = request.get_json()
        query = data['query']
        top_k = data['top_k']
        source = ''
        if 'source' in query:
            source = query['source']
        output = index.query(query, top_k=top_k, source=source)
        return jsonify(output), 200
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=config['port'])