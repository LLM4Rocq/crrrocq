import argparse
import json
import os
from copy import deepcopy


"""
Step 10: Duplicate entries to only keep at most one result per type of block (e.g. last search result + last script result)
"""

def split_compress(entry):
    splits = []
    cumulative_wo_result_search = []
    cumulative_wo_result_script = []
    cumulative_wo_result = []

    last_complete = []
    kind_result = ""
    for block in entry['blocks']:
        block['ignore'] = (block['kind'] == 'result')

        if block['kind'] in ['search', 'script']:
            kind_result = block['kind']

        if block['kind'] == 'result':
            if last_complete:
                splits.append({"name": entry['name'], "blocks": deepcopy(last_complete), "initial_goal": entry['initial_goal']})
                for block_aux in cumulative_wo_result_search:
                    block_aux['ignore'] = True
                for block_aux in cumulative_wo_result_script:
                    block_aux['ignore'] = True
                for block_aux in last_complete:
                    block_aux['ignore'] = True
            if kind_result == 'search':
                cumulative_wo_result_script = cumulative_wo_result + [block]
                last_complete = cumulative_wo_result_search + [block]
            else:
                cumulative_wo_result_search = cumulative_wo_result + [block]
                last_complete = cumulative_wo_result_script + [block]
        else:
            cumulative_wo_result_script.append(block)
            cumulative_wo_result_search.append(block)
            cumulative_wo_result.append(block)
            last_complete.append(block)
    if entry['blocks'][-1]['kind'] != 'result':
        splits.append({"name": entry['name'], "blocks": last_complete, "initial_goal": entry['initial_goal']})
    return splits


        
def blocks_to_str(blocks):
    result = ""
    for block in blocks:
        result += f'{block["kind"]}\n{block["content"]}\n\n'
    return result

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default='export/output/steps/step_9/result.json')
    parser.add_argument('--output', default='export/output/steps/step_10/')

    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    with open(args.input, 'r') as file:
        content = json.load(file)

    export = []
    for entry in content:
        export += split_compress(entry)
    with open(os.path.join(args.output, 'result.json'), 'w') as file:
        json.dump(export, file, indent=4)
