import argparse
import os
import json
from collections import defaultdict

from transformers import AutoTokenizer
from tqdm import tqdm
from vllm import LLM, SamplingParams

from src.training.dataset import load_and_process

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-dataset', default='export/', help='Dataset')
    parser.add_argument('--input-sources', default='export/steps/sources', help='Directory containing sources files')
    parser.add_argument('--model-path', default='/lustre/fsn1/projects/rech/mmr/ulu88xb/babel/checkpoint-epoch-3', help='Dataset')
    parser.add_argument('--tokenizer-path', default='/lustre/fsn1/projects/rech/mmr/ulu88xb/models/Qwen-32B', help='Dataset')

    parser.add_argument('--prompt-path', default='src/training/prompts/prompt.json', help='Dataset')
    parser.add_argument('--output', default='export/eval', help='Output directory')
    parser.add_argument('--dataset-entry', default='validation', help='Entry to use in the dataset')
    parser.add_argument('--k', type=int, default=64, help='Number of generation per entry')
    parser.add_argument('--temperature', type=float, default=0.6, help='Temperature')
    parser.add_argument('--top-p', type=float, default=0.95, help='Top-p')
    parser.add_argument('--max-tokens', type=int, default=4096, help='Max output len')
    parser.add_argument('--gpus', type=int, default=4, help='Number of gpus')
    args = parser.parse_args()
    
    os.makedirs(args.output, exist_ok=True)

    path_output_temp = args.output + '_temp'
    os.makedirs(path_output_temp, exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer_path)

    dataset = load_and_process(tokenizer, args.input_dataset, args.prompt_path)
    llm = LLM(model=args.model_path, tokenizer=args.tokenizer_path, max_model_len=12_000, tensor_parallel_size=args.gpus, dtype="bfloat16", gpu_memory_utilization=0.98, trust_remote_code=True)

    sampling_params = SamplingParams(temperature=args.temperature, max_tokens=args.max_tokens, top_p=args.top_p)
    sampling_params.n = args.k  # This tells vLLM to generate k completions per prompt.
    result = defaultdict(lambda:defaultdict(list))

    for entry in tqdm(dataset[args.dataset_entry]):
        filepath = os.path.join(path_output_temp, entry['name']+'.json')
        if os.path.exists(filepath):
            continue
        # Convert token IDs back into text.
        prompt_text = tokenizer.decode(entry['input_ids'], skip_special_tokens=True)
        # Generate output completions.
        outputs = llm.generate([prompt_text], sampling_params)
        # Each output in "outputs" is a RequestOutput object containing a list of completions.
        for output in outputs:
            for completion in output.outputs:
                result.append(completion.text)
        
        new_entry = {"name": entry['name'], "repository": entry['repository'], "workspace": entry['workspace'], "filepath": entry['filepath'], "outputs": [{"content": content} for content in result]}
        with open(filepath, 'w') as file:
            json.dump(new_entry, file, indent=4)
        
        result[entry['repository']][entry['category']].append(new_entry)
    

    for repository in result:
        for category in result[repository]:
            filepath = os.path.join(args.output, repository, f'{category}.json')
            with open(filepath, 'w') as file:
                json.dump({"category": category, "thms": result[category]}, file, indent=4)
    