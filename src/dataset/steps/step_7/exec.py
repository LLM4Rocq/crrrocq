import argparse
import json
import os
import re
import concurrent.futures
import time
import random

import yaml
from openai import OpenAI
from tqdm import tqdm

"""
Step 7: Generate new query when failed search.
"""

class MissingBlock(Exception):
    pass

def parse_output(output: str, expected_len=5):
    pattern = re.compile(
        r"<(?P<kind>\w+)>\s*(?P<content>.*?)\s*<\/\1>",
        re.DOTALL | re.MULTILINE,
    )
    block_think = {}
    block_search = {"kind": "searchs", "content": []}
    for m in pattern.finditer(output):
        if m.group("kind") == "think":
            block_think = {
                "kind": "think",
                "content": m.group("content").strip()
            }
        elif m.group("kind") == "search":
            block_search['content'].append( m.group("content").strip())
    if not block_think or len(block_search['content']) < expected_len:
        raise MissingBlock
    return block_think, block_search

def generate_output(prompt, client, config):
    """
    Sends prompt to client using config.
    """
    completion = client.chat.completions.create(
        messages=[
            {"role": "user", "content": prompt}
        ],
        **config
    )
    return parse_output(completion.choices[0].message.content)

def query(entry, client, config, prompt_template, prompt_template_have, export_path, delay=0, top_k=10, retry=3):
    """Query the LLM for better search queries."""
    if not 'output_blocks' in entry:
        return 
    time.sleep(delay)
    dependencies = []
    for eval in entry['evaluation']:
        for c in eval['dependencies']:
            if 'info' in c and 'docstring' in c['info']:
                dependencies.append((c['name'], c['info']['fullname'], c['info']['docstring'], 'force_result' in c))

    blocks = entry['output_blocks']
    new_blocks = []
    for block_prev, block_next, block_next_next in zip(blocks, blocks[1:], blocks[2:]):
        new_blocks.append(block_prev)
        if not block_prev['kind'] == 'search':
            continue
        wrong_query = block_prev['content']
        search_result = block_prev['search_result']
        first_result = ""
        for _, element, _ in search_result[:top_k]:
            first_result += element['fullname'] + '\n its docstring: ' + element['docstring'] + '\n\n'
        
        if block_next_next['kind'] == 'have':
            prompt = prompt_template_have.format(wrong_query=wrong_query, first_result=first_result)
            success = False
            for _ in range(retry):
                try:
                    block_think, block_search = generate_output(prompt, client, config)
                    new_blocks += [block_think, block_search]
                    success = True
                    break
                except MissingBlock:
                    print("Missing block issue, retry")
            
            if not success:
                raise MissingBlock
            continue
        targets = []
        docstrings = []
        fullnames = []

        for dep, fullname, docstring, force_result in dependencies:
            match = re.search(re.escape(str(dep)), block_next['content'])
            if match:
                targets.append((match.start(), {'name': dep, 'force_result': force_result}))
                docstrings.append((match.start(), docstring))
                fullnames.append((match.start(), fullname))
        
        if not targets:
            continue
        

        targets.sort(key=lambda x:x[0])
        targets = [s for _,s in targets]

        docstrings.sort()
        docstrings = [d for _,d in docstrings]

        fullnames.sort()
        fullnames = [f for _,f in fullnames]
        
        block_prev['target'] = targets[0]
        
        found = False

        target_lemma = fullnames[0] + '\n its docstring: ' + docstrings[0]
        think_block_correct = block_next['content']
        
        if targets[0]['force_result']:
            continue
        for _, element, _ in search_result[:top_k]:
            if element['name'] in targets[0]['name']:
                found = True
        if not found:
            prompt = prompt_template.format(wrong_query=wrong_query, target_lemma=target_lemma, first_result=first_result, think_block_correct=think_block_correct)
            success = False
            for _ in range(retry):
                try:
                    block_think, block_search = generate_output(prompt, client, config)
                    block_search['target'] = block_prev['target']
                    new_blocks += [block_think, block_search]
                    success = True
                    break
                except MissingBlock:
                    print("Missing block issue, retry")
            
            if not success:
                raise MissingBlock
    new_blocks += blocks[-2:]
    entry['output_blocks'] = new_blocks
    with open(export_path, 'w') as file:
        json.dump(entry, file, indent=4)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input',  default='export/output/steps/step_7/result.json')
    parser.add_argument('--output',  default='export/output/steps/step_8/')
    parser.add_argument('--config-dir', default='src/dataset/steps/step_8/')
    parser.add_argument('--top-k', default=10, help="Top-k parameter use for retrieval", type=int)
    parser.add_argument('--max-workers', default=100, type=int, help='Max number of concurrent workers')
    parser.add_argument('--mean-delay', default=10, type=int, help='Mean delay before a request is send: use this parameter to load balance')

    args = parser.parse_args()

    output_aux = os.path.join(args.output, 'aux')
    os.makedirs(output_aux, exist_ok=True)

    with open(args.input, 'r') as file:
        content = json.load(file)

    config_path = os.path.join(args.config_dir, 'config.yaml')
    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)

    prompt_path = os.path.join(args.config_dir, 'prompt.txt')
    with open(prompt_path, 'r') as file:
        prompt_template = file.read()

    prompt_have_path = os.path.join(args.config_dir, 'prompt_have.txt')
    with open(prompt_have_path, 'r') as file:
        prompt_template_have = file.read()
    
    client = OpenAI(
        base_url=config['base_url'],
        api_key=os.getenv("OPENAI_API_KEY")
    )
    to_do = []
    for fqn, entry in content.items():
        export_path = os.path.join(output_aux, f"{fqn.replace('.', '_')}.json")
        entry['fqn'] = fqn
        if not os.path.exists(export_path):
            to_do.append((entry, export_path))

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = [executor.submit(query, entry, client, config['request_config'], prompt_template, prompt_template_have, export_path, delay=random.randint(0, 2*args.mean_delay), top_k=args.top_k) for entry, export_path in to_do]
        for _ in tqdm(concurrent.futures.as_completed(futures), total=len(futures)):
            pass
    
    result = {}
    for filename in os.listdir(output_aux):
        with open(os.path.join(output_aux, filename), 'r') as file:
            content = json.load(file)
        result[content['fqn']] = content

    with open(os.path.join(args.output, 'result.json'), 'w') as file:
        json.dump(result, file, indent=4)