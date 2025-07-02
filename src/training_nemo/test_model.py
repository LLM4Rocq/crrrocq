import json
import argparse
import random
import re
import os

from transformers import AutoTokenizer, AutoModelForCausalLM, StoppingCriteria, StoppingCriteriaList
import torch

from src.embedding.index.cosim_index import FaissIndex
from src.embedding.models.factory import get_embedding_model

class ParsingBlockError(Exception):
    pass

class GenerationStopper(StoppingCriteria):
    def __init__(self, stop_tokens: dict[str, list[int | list[int]]]):
        self.stop_token_ids = []
        self.stop_token_words = []
        for k, t in stop_tokens.items():
            if any(isinstance(x, list) for x in t):  # if t is nested list
                for x in t:
                    self.stop_token_ids.append(torch.tensor(x))
                self.stop_token_words.append(k)
            else:
                self.stop_token_ids.append(torch.tensor(t))
                self.stop_token_words.append(k)
            assert isinstance(t, list) or isinstance(t, int)

    def __repr__(self):
        return f"Stopping words: {self.stop_token_words}"

    def __call__(
        self, input_ids: torch.LongTensor, scores: torch.FloatTensor, **kwargs
    ) -> bool:
        for t in self.stop_token_ids:
            if torch.eq(input_ids[0][-len(t) :].to("cpu"), t).all():
                return True
        return False

    @property
    def criteria(self):
        return StoppingCriteriaList([self])

def parse_output(output: str, max_len=2):
    pattern = re.compile(
        r"<(?P<kind>\w+)>\s*(?P<content>.*?)\s*<\/\1>",
        re.DOTALL | re.MULTILINE,
    )
    result = []
    for m in pattern.finditer(output):
        kind = m.group("kind").strip()
        if kind not in ['search', 'think', 'script', 'have']:
            raise ParsingBlockError
        block = {
            "kind": m.group("kind").strip(),
            "content": m.group("content").strip()
        }
        result.append(block)
    if max_len < len(result):
        raise ParsingBlockError
    return result

def search_result_to_str(search_result):
    output = "<result>\n"
    for k, (_, element, _) in enumerate(search_result, start=1):
        fullname, docstring = element['fullname'], element['docstring']
        output += f"{k}. {fullname}\n{docstring}\n\n"
    # TODO: retrain with clean format
    output += "\n</result>\n"
    return output

parser = argparse.ArgumentParser()
parser.add_argument('--evaluation-path',  default='/lustre/fsn1/projects/rech/tdm/commun/dataset/evaluation.json', help='Evaluation set path')
parser.add_argument('--prompt-path', default='/lustre/fsn1/projects/rech/tdm/commun/dataset/prompt.json', help='Prompt path')
parser.add_argument('--docstrings-path', default='/lustre/fsn1/projects/rech/tdm/commun/dataset/docstrings.json', help='Docstrings path')
parser.add_argument('--embedding-cache-path', default='/lustre/fsn1/projects/rech/tdm/commun/cache/', help='Embedding cache path')

parser.add_argument('--embedding-model', default='qwen_embedding_4b', help="Embedding model's name")
parser.add_argument('--atp-path', default='/lustre/fsn1/projects/rech/tdm/commun/models/crrrocq_base/', help="Embedding model's name")

parser.add_argument('--device-embedding', default='cuda:0', help="Device for embedding model")
parser.add_argument('--device-atp', default='cuda:0', help="Device for crrrocq model")

parser.add_argument('--batch-size', default=32, help="Batch size used to pre compute embedding", type=int)
parser.add_argument('--top-k', default=10, help="Top-k parameter use for retrieval", type=int)

args = parser.parse_args()

with open(args.prompt_path, 'r') as file:
    prompt = json.load(file)
with open(args.docstrings_path, 'r') as file:
    docstrings = json.load(file)
with open(args.evaluation_path, 'r') as file:
    evaluation = json.load(file)

model = get_embedding_model(args.embedding_model, device=args.device_embedding)
index = FaissIndex(model, docstrings, batch_size=args.batch_size, cache_path=args.embedding_cache_path)
tokenizer = AutoTokenizer.from_pretrained(args.atp_path)
model = AutoModelForCausalLM.from_pretrained(
    args.atp_path,
    torch_dtype="auto",
    device_map=args.device_atp
)
tags = ['</search>\n', '</script>\n', '</have>\n']
stop_tokens = {tag: tokenizer(tag)['input_ids'] for tag in tags}
stopper = GenerationStopper(stop_tokens)

PROMPT_TEMPLATE = prompt['instruction']

entries = list(evaluation.values())
os.system('clear')
while True:
    entry = random.choice(entries)
    print(entry['statement'])
    print(entry['initial_goal'])
    prompt = PROMPT_TEMPLATE.format(initial_goal=entry['initial_goal'])
    messages = [
        {"role": "user", "content": prompt}
    ]
    prefix_text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    ongoing = True

    while ongoing:
        os.system('clear')
        print(prefix_text)
        input('Continue?')
        input_ids = tokenizer(prefix_text, return_tensors="pt").to(model.device)
        output_ids = model.generate(**input_ids, stopping_criteria=stopper.criteria, max_new_tokens=768)
        text = tokenizer.decode(output_ids[0])
        new_chunk = text[len(prefix_text):]
        blocks = parse_output(new_chunk)
        if not blocks:
            prefix_text = text
            ongoing = False
            continue
        if blocks[-1]['kind'] == 'search':
            search_query = blocks[-1]['content']
            search_result = index.query(search_query, top_k=args.top_k)
            prefix_text += new_chunk + search_result_to_str(search_result)
        else:
            prefix_text += f"<{blocks[-1]['kind']}>\n{blocks[-1]['content']}</{blocks[-1]['kind']}>"
            ongoing = False
    
    os.system('clear')
    print(prefix_text)
    input('New entry?')
            
