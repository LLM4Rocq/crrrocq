import re
import json
import argparse
import random
import os
from typing import List
from pathlib import Path

import bm25s
import numpy as np
from tqdm import tqdm

from dataset.parser.chains import proof_to_chain_list, number_of_tactics_chain

"""
Step 3: Extract a diverse set of theorems using BM25.
"""

def extract_have_proofs(theorem):
    """Extract all have proofs a theorem has."""
    matches = re.finditer(r"\(\*<have>\*\)[\s\S]*?\(\*<\/have>\*\)", theorem["proof"])
    return [match.group(0) for match in matches]

def number_of_tactics_have_proof(have_proof):
    """Compute the number of tactics in a have proof."""
    chain_list = proof_to_chain_list(have_proof)
    number_of_tactics = sum(map(number_of_tactics_chain, chain_list))
    return number_of_tactics

def number_of_tactics(proof):
    "computer number of tactics in a proof (outside of have block)"
    proof = proof.replace('Proof.', '').replace('Qed.', '') + ' '
    return len(re.findall(r'\.\s', proof))

def select_diverse_documents(documents: List[str], top_k):
    """
    Extracts subset of diverse documents using BM25.
    
    return index of selected documents
    """
    # Not efficient, but enough for the moment
    retriever = bm25s.BM25(corpus=documents)
    retriever.index(bm25s.tokenize(documents))
    similarity_matrix = np.zeros((len(documents), len(documents)))
    
    for i, doc in tqdm(enumerate(documents)):
        tokenized_doc = bm25s.tokenize(doc)
        scores = retriever.retrieve(tokenized_doc, k=len(documents)).scores
        similarity_matrix[i, :] = scores

    selected_indices = [random.randint(0, len(documents)-1)]  # Start with a random document
    with tqdm(total=top_k) as pbar:
        while len(selected_indices) < top_k:
            min_similarities = []
            
            for i in range(len(documents)):
                if i not in selected_indices:
                    min_sim = min(similarity_matrix[i, selected_indices])
                    min_similarities.append((i, min_sim))
            next_doc = min(min_similarities, key=lambda x: x[1])[0]
            selected_indices.append(next_doc)
            pbar.update(1)
    
    return selected_indices

def make(dataset, k_have=500, k_wo_have=500, max_number_of_tactics=14, min_number_of_tactics=2):
    """Select theorems using bm25"""

    datafile = Path(dataset)
    if not datafile.exists():
        raise Exception(f"Error: {dataset} doesn't exist.")
    with open(datafile, 'r') as file:
        theorems = json.load(file)

    with_have = [qn for qn, theorem in theorems.items() if "*<have>*)" in theorem['proof']]
    with_have = [qn for qn in with_have if min_number_of_tactics <= number_of_tactics(theorems[qn]['proof']) <= max_number_of_tactics]

    without_have = [qn for qn, theorem in theorems.items() if "*<have>*)" not in theorem['proof']]
    without_have = [qn for qn in without_have if min_number_of_tactics <= number_of_tactics(theorems[qn]['proof']) <= max_number_of_tactics]

    assert len(with_have) >= k_have, f'Not enough theorems with have satisfying conditions {min_number_of_tactics} <= number_of_tactics <= {max_number_of_tactics}'
    assert len(without_have) >= k_wo_have, f'Not enough theorems satisfying conditions {min_number_of_tactics} <= number_of_tactics <= {max_number_of_tactics}'

    documents_with_have = [theorems[qn]['statement'] for qn in with_have]
    documents_without_have = [theorems[qn]['statement'] for qn in without_have]

    result = {}
    print("Select diverse set of theorems with have blocks")
    for idx in select_diverse_documents(documents_with_have, top_k=k_have):
        qn = with_have[idx]
        result[qn] = theorems[qn]
    print("Select diverse set of theorems without have block")
    for idx in select_diverse_documents(documents_without_have, top_k=k_wo_have):
        qn = without_have[idx]
        result[qn] = theorems[qn]
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Select theorems in a dataset.")
    parser.add_argument("--input", type=str, default="export/output/steps/step_2/result.json", help="The path to the previous step")
    parser.add_argument("--output", type=str, default="export/output/steps/step_3/", help="Output path")
    parser.add_argument("--k-have", type=int, default=500, help="Number of theorems with have blocks")
    parser.add_argument("--k-wo-have", type=int, default=500, help="Number of theorems without have blocks")

    args = parser.parse_args()
    os.makedirs(args.output, exist_ok=True)
    result = make(args.input, k_have=args.k_have, k_wo_have=args.k_wo_have)
    
    with open(os.path.join(args.output, 'result.json'), 'w') as file:
        json.dump(result, file, indent=4)