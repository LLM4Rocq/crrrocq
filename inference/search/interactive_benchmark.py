import json
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search.embedding_model import MxbaiEmbedding
from search.cosim_index import FaissIndex


prompt_template = """You are working on a MathComp/Coq proof.  

Goal:
{proposition}

Proof steps:
{steps}

Available lemmas and constants:
{constants}

Imagine you don’t yet know which lemma to apply.  
1. Describe how you’d reason from the goal and proof step to identify which lemma or constant you need.  
2. Then write the single, concise natural-language question you would pose to a retrieval system to find that lemma or constant—without naming it.

Format your answer as:

Reasoning: <your chain-of-thought> 
Target: <name of the target> 
Query: <your retrieval query>"""


embedding_pt_path= 'dataset/embedding/pt'
benchmark_path = 'dataset/mathcomp/mxpoly'

model = MxbaiEmbedding()
index = FaissIndex(model, embedding_pt_path)

for filename in os.listdir(benchmark_path):
    filepath = os.path.join(benchmark_path, filename)
    if not filename.startswith('term_'):
        continue

    with open(filepath, 'r') as file:
        content = json.load(file)
    
    filtered_constants = [c.split('\n')[0] for c in content['constants']]
    filtered_constants = [c for c, c2 in zip(content['constants'], filtered_constants) if c2 in index.all_keys]

    data = {
            "proposition": content["proposition"],
            "steps": "\n".join(content['steps']),
            "constants": "\n".join(filtered_constants)
        }
    prompt = prompt_template.format(**data)
    print(prompt)
    query = input('Query:')
    result = index.query(query)

    for score, key, docstring in result:
        print(score, key)
        print(docstring)
        print()