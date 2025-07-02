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

class MissingBlock(Exception):
    pass

"""
Step 6: Add missing docstrings to dependencies.
"""

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
    return json.loads(completion.choices[0].message.content)

def query(fullname, fqn, client, config, prompt_template, export_path, delay=0, retry=3):
    time.sleep(delay)
    
    prompt = prompt_template.format(fullname=fullname)
    for _ in range(retry):
        try:
            output = generate_output(prompt, client, config)
            break
        except MissingBlock:
            pass
    output['fqn'] = fqn
    output['fullname'] = fullname
    with open(export_path, 'w') as file:
        json.dump(output, file, indent=4)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input',  default='export/output/steps/step_5/')
    parser.add_argument('--dictionary', default='export/docstrings/dictionary.json', help='Database path')
    parser.add_argument('--output',  default='export/output/steps/step_6/')
    parser.add_argument('--config-dir', default='src/dataset/steps/step_6/')
    parser.add_argument('--max-workers', default=100, type=int, help='Max number of concurrent workers')
    parser.add_argument('--mean-delay', default=10, type=int, help='Mean delay before a request is send: use this parameter to load balance')

    args = parser.parse_args()

    output_aux = os.path.join(args.output, 'aux')
    os.makedirs(output_aux, exist_ok=True)

    with open(os.path.join(args.input, 'result.json'), 'r') as file:
        input_content = json.load(file)

    config_path = os.path.join(args.config_dir, 'config.yaml')
    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)

    prompt_path = os.path.join(args.config_dir, 'prompt.txt')
    with open(prompt_path, 'r') as file:
        prompt_template = file.read()
    
    client = OpenAI(
        base_url=config['base_url'],
        api_key=os.getenv("OPENAI_API_KEY")
    )
    to_do = set()

    for fqn, entry in input_content.items():
        for eval in entry['evaluation']:
            for c in eval['dependencies']:
                if 'info' not in c or 'docstring' not in c['info']:
                    fullname = f"Lemma {c['name']}: {c['type']}"
                    fqn = c['fqn']
                    export_path = os.path.join(output_aux, f"{fqn.replace('.', '_')}.json")
                    if not os.path.exists(export_path):
                        to_do.add((fullname, fqn, export_path))

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = [executor.submit(query, fullname, fqn, client, config['request_config'], prompt_template, export_path, delay=random.randint(0, 2*args.mean_delay)) for fullname, fqn, export_path in to_do]
        for _ in tqdm(concurrent.futures.as_completed(futures), total=len(futures)):
            pass
    
    result = {}
    
    for filename in os.listdir(output_aux):
        with open(os.path.join(output_aux, filename), 'r') as file:
            content = json.load(file)
        result[content['fqn']] = content

    for fqn, entry in input_content.items():
        for eval in entry['evaluation']:
            for c in eval['dependencies']:
                if 'info' not in c or 'docstring' not in c['info']:
                    c['info'] = result[c['fqn']]
                    c['force_result'] = True
    
    with open(os.path.join(args.output, 'result.json'), 'w') as file:
        json.dump(input_content, file, indent=4)

    with open(os.path.join(args.output, 'new_docstring.json'), 'w') as file:
        json.dump(result, file, indent=4)