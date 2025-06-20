import argparse
import json
import os
from copy import deepcopy
import re
import random

from tqdm import tqdm

from src.embedding_models.gteqwen import GteQwenEmbedding
from src.embedding_models.mxbai import MxbaiEmbedding
from src.embedding_models.qwen_embedding import Qwen3Embedding600m, Qwen3Embedding4b, Qwen3Embedding8b
from src.index.cosim_index import FaissIndex

DICT_MODEL = {
    "gte_qwen": GteQwenEmbedding,
    "mxbai": MxbaiEmbedding,
    "qwen_embedding_600m": Qwen3Embedding600m,
    "qwen_embedding_4b": Qwen3Embedding4b,
    "qwen_embedding_8b": Qwen3Embedding8b,
}

def parse_output(output: str):
    pattern = re.compile(
        r"<(?P<kind>\w+)>\s*(?P<content>.*?)\s*</\1>",
        re.DOTALL | re.MULTILINE,
    )
    blocks = []
    for m in pattern.finditer(output):
        blocks.append({
            "kind": m.group("kind"),
            "content": m.group("content").strip()
        })

    return blocks

def filter_best_search(block):
    assert block['kind'] == 'searchs', 'Block must be a "searchs" (*plural*) block'
    k = random.randint(0, len(block['content']) - 1)
    if 'target' in block:
        target = block['target']['name']
        best_rank = float('inf')
        for k_aux, search_result in enumerate(block['searchs_result']):
            for rank, (_, element, _) in enumerate(search_result):
                if element['name'] == target:
                    if rank < best_rank:
                        best_rank
                        k = k_aux
    block['kind'] = "search"
    block['content'] = block['content'][k]
    block['search_result'] = block['searchs_result'][k]
    del block['searchs_result']

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input',  default='export/output/steps/step_5_bis/result.json')
    parser.add_argument('--dictionary', default='export/docstrings/dictionary.json', help='Database path')
    parser.add_argument('--output',  default='export/output/steps/step_6/')
    parser.add_argument('--model-name', default='qwen_embedding_4b', help="Embedding model's name")
    parser.add_argument('--device', default='cpu', help="Device for embedding model")
    parser.add_argument('--batch-size', default=32, help="Batch size used to pre compute embedding", type=int)
    parser.add_argument('--top-k', default=20, help="Top-k parameter use for retrieval", type=int)
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    with open(args.dictionary, 'r') as file:
        dictionary = json.load(file)
    
    with open(args.input, 'r') as file:
        content = json.load(file)
    
    model = DICT_MODEL[args.model_name](device=args.device)
    index = FaissIndex(model, dictionary, batch_size=args.batch_size)

    for entry in tqdm(list(content.values())):
        if 'output_blocks' not in entry:
            entry['output_blocks'] = parse_output(entry['CoT'])
        blocks = entry['output_blocks']
        for block in blocks:
            if block['kind'] == 'search':
                if 'search_result' not in block:
                    block['search_result'] = index.query(block['content'], top_k=3*args.top_k)
            if block['kind'] == 'searchs':
                if 'search_result' not in block:
                    block['searchs_result'] = [index.query(content, top_k=3*args.top_k) for content in block["content"]]
                filter_best_search(block)
    with open(os.path.join(args.output, 'result.json'), 'w') as file:
        json.dump(content, file, indent=4)