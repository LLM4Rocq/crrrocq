import argparse
import json
import os

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

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input',  default='export/output/steps/step_5_bis/result.json')
    parser.add_argument('--dictionary', default='export/docstrings/dictionary.json', help='Database path')
    parser.add_argument('--output',  default='export/output/steps/step_6/')
    parser.add_argument('--model-name', default='qwen_embedding_4b', help="Embedding model's name")
    parser.add_argument('--device', default='cuda:0', help="Device for embedding model")
    parser.add_argument('--batch-size', default=32, help="Batch size used to pre compute embedding", type=int)
    parser.add_argument('--top-k', default=10, help="Top-k parameter use for retrieval", type=int)
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    with open(args.dictionary, 'r') as file:
        dictionary = json.load(file)
    
    with open(args.input, 'r') as file:
        content = json.load(file)
    
    model = DICT_MODEL[args.model_name](device=args.device)
    index = FaissIndex(model, dictionary, batch_size=args.batch_size)

    while(True):
        os.system('clear')
        query = input("Query: ")
        for _, entry, _ in index.query(query, top_k=args.top_k):
            print(bcolors.OKGREEN + entry['name'] + bcolors.ENDC)
            print(bcolors.WARNING + entry['docstring'] + bcolors.END)
            print()
            print()

