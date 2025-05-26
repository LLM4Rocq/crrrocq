import re
import json
import argparse
from pathlib import Path

from parser.chains import proof_to_chain_list, number_of_tactics_chain

list_selectors = {
    "first": lambda l, n: l[:n],
    "half": lambda l, n: l[len(l)//2-n//2:len(l)//2+n//2],
    "last": lambda l, n: l[-n:],
    "9-10th": lambda l, n: l[9*len(l)//10-n//2:9*len(l)//10+n//2],
    "19-20th": lambda l, n: l[19*len(l)//20-n//2:19*len(l)//20+n//2],
}

def extract_have_proofs(theorem):
    """Extract all have proofs a theorem has."""
    matches = re.finditer(r"\(\*<have>\*\)[\s\S]*?\(\*<\/have>\*\)", theorem["proof"])
    return [match.group(0) for match in matches]

def number_of_tactics_have_proof(have_proof):
    """Compute the number of tactics in a have proof."""
    chain_list = proof_to_chain_list(have_proof)
    number_of_tactics = sum(map(number_of_tactics_chain, chain_list))
    return number_of_tactics

def select_have(theorems, total, share, select_with, select_without):
    """Select the theorems with have."""
    assert (0 <= share <= 1)

    with_have = [qn for qn, theorem in theorems.items() if theorem["proof"].find("(*<have>*)") >= 0]
    with_have = [(extract_have_proofs(theorems[qn]), qn) for qn in with_have]
    with_have = [(list(map(number_of_tactics_have_proof, haves)), qn) for haves, qn in with_have]
    with_have = [(sum(lnot) / len(lnot), len(lnot), theorems[qn]["score"], qn) for lnot, qn in with_have]
    max_mean_haves_size = max(*[m for m, _, _, _ in with_have])
    max_nbr_haves       = max(*[n for _, n, _, _ in with_have])
    max_scores          = max(*[s for _, _, s, _ in with_have])
    with_have = [(m/max_mean_haves_size + n/max_nbr_haves + s/max_scores, qn) for m, n, s, qn in with_have]
    with_have.sort()
    with_have = list_selectors[select_with](with_have, int(total * share))

    without_have = [(theorem["score"], qn) for qn, theorem in theorems.items() if theorem["proof"].find("(*<have>*)") < 0]
    without_have.sort()
    without_have = list_selectors[select_without](without_have, total - len(with_have))

    return {qn: theorems[qn] for _, qn in with_have} | {qn:theorems[qn] for _, qn in without_have}

selectors = {
    "1000_0.5_first_19-20th": lambda theorems: select_have(theorems, 1_000, 0.5, "first", "19-20th")
}

def make(dataset, selector):
    """Select theorems with the given `selector` and save them."""

    datafile = Path(dataset)
    if not datafile.exists():
        raise Exception(f"Error: {dataset} doesn't exist.")
    savefile = Path(datafile.parent, datafile.stem + "_" + selector + ".json")

    if savefile.exists():
        print("Selected dataset already here.")
    else:

        print("Making the selected dataset:")

        print("  Download all the theorems ...")
        with open(datafile, "r") as f:
            theorems = json.load(f)

        print("  Select theorems ...")
        theorems = selectors[selector](theorems)

        print("  Saving the selected data ...")
        with open(savefile, "w") as f:
            json.dump(theorems, f, indent=2)

        print("  DONE!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Select theorems in a dataset.")
    parser.add_argument("--dataset", type=str, default="mathcomp_bm25_have.json", help="The path of the dataset, default is 'mathcomp_bm25_have.json'")
    parser.add_argument("--selector", type=str, default="1000_0.5_first_19-20th", help="The selection algorithm to use, it can be chosen among: " + ", ".join(selectors.keys()))
    args = parser.parse_args()
    make(args.dataset, args.selector)
