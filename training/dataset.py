import os
from functools import partial
import json
import argparse
import re

from transformers import AutoTokenizer
import torch
from datasets import load_dataset

def pad_sequences(sequences, pad_value, pad_first=False):
    """
    Pads a list of sequences (lists of ints) to the same length using pad_value.
    """
    max_length = max(len(seq) for seq in sequences)
    if pad_first:
        return torch.tensor([[pad_value] * (max_length - len(seq)) + seq for seq in sequences])
    else:
        return torch.tensor([seq + [pad_value] * (max_length - len(seq)) for seq in sequences])

def list_of_dict_to_dict(lst):
    if not lst:
        return {}
    result = {key:[] for key in lst[0].keys()}
    for dct in lst:
        for key in dct:
            result[key].append(dct[key])
    return result

def merge_and_pad_entries(entries, pad_value, pad_first=False):
    merge_entries = list_of_dict_to_dict(entries)
    keys = ['input_ids', 'attention_mask', 'labels']
    result = {key: pad_sequences(merge_entries[key], pad_value, pad_first=pad_first) for key in keys}
    return result

def only_keep_columns(dataset, columns):
    for key in dataset:
        cols_to_remove = dataset[key].column_names
        [cols_to_remove.remove(column) for column in columns]
        dataset[key] = dataset[key].remove_columns(cols_to_remove)

def preprocess_dataset(tokenizer, entry):
    input_ids_list_before = tokenizer(entry['before'], add_special_tokens=False)
    input_ids_list_end = tokenizer(entry['end'], add_special_tokens=False)
    input_ids_list_sep = tokenizer(entry['sep'], add_special_tokens=False)

    num_example = len(input_ids_list_before['input_ids'])
    input_ids_list = []
    labels_list = []
    attn_mask_list = []
    for i in range(num_example):
        before_ids = input_ids_list_before['input_ids'][i]
        sep_ids = input_ids_list_sep['input_ids'][i]
        end_ids = input_ids_list_end['input_ids'][i]

        input_ids = before_ids + sep_ids
        labels_id = [-100] * (len(before_ids) + len(sep_ids))

        tag_ids_list = tokenizer(entry['tags'][i])
        content_ids_list = tokenizer(entry['contents'][i])

        for k, tag in enumerate(entry['tags'][i]):
            tag_ids = tag_ids_list['input_ids'][k]
            content_ids = content_ids_list['input_ids'][k]
            input_ids += tag_ids + content_ids
            if 'result' in tag:
                labels_id += tag_ids + [-100]*len(content_ids)
            else:
                labels_id += tag_ids + content_ids
        
        input_ids += end_ids
        labels_id += end_ids

        attn_mask_list.append([1]*len(input_ids))
        input_ids_list.append(input_ids)
        labels_list.append(labels_id)

    batch = {
        "input_ids": input_ids_list,
        "labels": labels_list,
        "attention_mask": attn_mask_list
    }
    return batch

def check_alignement(tokenizer, token_ids, sep, labels):
    sep_ids = tokenizer(sep, add_special_tokens=False)['input_ids']
    for i in range(len(token_ids) - len(sep_ids) + 1):
        if token_ids[i] == sep_ids[0]:
            if token_ids[i:i+len(sep_ids)] == sep_ids:
                for j in range(i + len(sep_ids)-1):
                    assert labels[j] == -100, "labels misaligned with respect to inputs_ids (sooner !=100 than expected)"
                for j in range(i+len(sep_ids)-1, len(token_ids)):
                    assert labels[j] != -100, "labels misaligned with respect to inputs_ids (=100 for too long)"
                return True
    raise Exception('Issue')

def load_and_process(tokenizer, data_path, prompt_path):
    with open(prompt_path, 'r') as file:
        prompt = json.load(file)

    dataset = load_dataset("json", data_files={
        'train': os.path.join(data_path, 'train.json'),
        # 'validation': os.path.join(data_path, 'validation.json'),
        # 'test': os.path.join(data_path, 'test.json')
    })

    dataset = dataset.map(lambda x: {
        "constants": "\n".join(x['constants']),
        "notations": "\n".join(x['notations'])
    })

    dataset['train'] = dataset['train'].map(lambda x: 
                                            {"tags": [f"\n\n<{block['tag']}>\n" for block in x['blocks']],
                                             "contents": [f"{block['content']}\n</{block['tag']}>" for block in x['blocks']],
                                             "sep": prompt["sep"],
                                             "before": prompt['text_before'].format(**x),
                                             "end": prompt['end']})

    # for entry in ['validation', 'test']:
    #     dataset[entry] = dataset[entry].map(lambda x: {"sep": prompt["sep"], "before": prompt['text_before'].format(**x), "after": ""})

    dataset = dataset.map(partial(preprocess_dataset, tokenizer), batched=True, batch_size=100)
    only_keep_columns(dataset, ['attention_mask', 'labels', 'input_ids', 'name', 'category'])
    return dataset


def extract_blocks(output):
    # Regular expression to match the tags and their content
    pattern = re.compile(r"<(result|think|search|script)>(.*?)</\1>", re.DOTALL)

    # Find all matches in order
    matches = pattern.findall(output)

    # Convert matches to a list of dictionaries or tuples if you want
    blocks = [{'tag': tag, 'content': content.strip()} for tag, content in matches]
    return blocks

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-path", type=str, default='dataset/')
    parser.add_argument("--prompt-path", type=str, default='training/prompts/prompt.json')
    parser.add_argument("--model-name", type=str, default="Qwen/Qwen2.5-1.5B-Instruct")
    args = parser.parse_args()

    tokenizer = AutoTokenizer.from_pretrained(
        args.model_name
    )

    dataset = load_and_process(tokenizer, args.data_path, args.prompt_path)
    
    for entry in dataset['train']:
        input_ids = entry['input_ids']
        for k, label in enumerate(entry['labels']):
            if label == -100:
                input_ids[k] = 0
        print(tokenizer.decode(entry["input_ids"]))
        input("continue?")