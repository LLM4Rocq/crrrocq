import argparse
import json
import os
from collections import defaultdict
from copy import deepcopy

import matplotlib.pyplot as plt
import numpy as np

def is_valid(entry, dictionary, top_k=10):
    entry_aux = deepcopy(entry)
    if not 'output_blocks' in entry_aux:
        return False, None

    fqn = entry['fqn'].replace('export.output.steps.step_0', 'mathcomp')
    fqn_clear = fqn.split('_have')[0]

    if fqn_clear not in dictionary:
        print(f"Ignore {fqn_clear}, missing from dictionary")
        return False, {}
    
    start_line, parent = dictionary[fqn_clear]['start_line'], dictionary[fqn_clear]['parent']
    dependencies = {}
    for eval in entry_aux['evaluation']:
        for c in eval['dependencies']:
            if 'info' in c and 'docstring' in c['info']:
                dependencies[c['name']] = c['info']

    blocks = entry_aux['output_blocks']
    
    target_found = defaultdict(lambda:False)

    for block_prev, block_next, block_next_next in zip(blocks, blocks[1:], blocks[2:]):
        if not block_prev['kind'] == 'search':
            continue
        
        if block_next['kind'] != 'think':
            return False, None
        
        filtered_search_result = []
        for score, element, fqn in block_prev['search_result']:
            fqn = fqn.replace('export.output.steps.step_0', 'mathcomp')
            if fqn in dictionary and dictionary[fqn]['parent'] == parent:
                if dictionary[fqn]['start_line'] >= start_line:
                    continue
            filtered_search_result.append((score, element, fqn))
        
        if len(filtered_search_result[:top_k]) < top_k:
            return False, {}
        block_prev['search_result'] = filtered_search_result[:top_k]
        search_result = block_prev['search_result']
        if block_next_next['kind'] == 'have' or 'target' not in block_prev:
            continue
        target = block_prev['target']['name']

        if block_prev['target']['force_result']:
            block_prev['search_result'] = [(1., dependencies[target], dependencies[target]['fqn'])] + search_result[1:]
            target_found[target] = True
            continue
        

        found = False
        
        for _, element, _ in search_result:
            if element['name'] == target:
                found = True
        
        if found and target_found[target]:
            return False, {}
        target_found[target] = found or target_found[target]

    
    is_all_okay = True
    for values in target_found.values():
        if not values:
            is_all_okay = False
    
    return is_all_okay, entry_aux

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default='export/output/steps/step_6/result.json')
    parser.add_argument('--dictionary', default='export/docstrings/dictionary.json', help='Database path')
    parser.add_argument('--top-k', type=int, default=10)
    parser.add_argument('--output', default='export/output/steps/step_7/')

    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    with open(args.input, 'r') as file:
        content = json.load(file)
    
    with open(args.dictionary, 'r') as file:
        dictionary = json.load(file)

    export = []
    hist = []
    for entry in content.values():
        valid, entry = is_valid(entry, dictionary, top_k=args.top_k)
        if not valid:
            continue
        output_blocks = entry['output_blocks']
        new_blocks = []
        num_script = 0
        has_have = False
        for block in output_blocks:
            new_blocks.append(block)
            if block['kind'] == 'search':
                new_block = {"kind": "result", "content": ""}
                search_result = block['search_result']
                for k, (_, element, _) in enumerate(search_result, start=1):
                    fullname, docstring = element['fullname'], element['docstring']
                    new_block['content'] += f"{k}. {fullname}\n{docstring}\n\n"
                del block['search_result']
                new_blocks.append(new_block)
            if block['kind'] == 'script':
                num_script += 1
            if block['kind'] == 'have':
                has_have = True
        if '_have' not in entry['fqn'] and not has_have:
            hist.append(num_script)
        block_output = {"name": entry['fqn'], "blocks": new_blocks}
        export.append(block_output)
    
    with open(os.path.join(args.output, 'result.json'), 'w') as file:
        json.dump(export, file, indent=4)

    hist = np.array(hist)

    bins = np.arange(hist.min(), hist.max() + 2)  # +2 so last integer included
    plt.hist(hist, bins=bins, align="left", rwidth=0.8, label="Proof lengths for proof without have")
    plt.xlabel("Length of proof")
    plt.ylabel("Count")
    plt.legend()
    plt.show()