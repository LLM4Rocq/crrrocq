import bm25s
import json
import argparse
from pathlib import Path
from tqdm import tqdm

def bm25_get_scores(theorems):
    """Compute bm25 scores of a dataset of theorems."""
    stemmer = lambda l: [word for word in l]

    tokenized_theorems = []
    for theorem in theorems:
        tokenized_theorems.append((theorem, bm25s.tokenize(theorem["statement"] + "\n" + theorem["proof"], return_ids=False, stemmer=stemmer)[0]))

    bm25 = bm25s.BM25()

    def get_score(thm, thms):
        thms = [t for _, t in thms]
        bm25.index(thms, show_progress=False)
        scores = bm25.get_scores(thm)
        score = sum(scores)

        return score

    scored_theorems = []
    for theorem, theorem_code in tqdm(tokenized_theorems):
        score = get_score(theorem_code, tokenized_theorems)
        scored_theorems.append(theorem | {"score": float(score)})

    return scored_theorems

scorers = {
    "bm25": bm25_get_scores
}

def make(dataset, scorer):
    """
    Read all Rocq files in the `dataset` and save all theorems.
    Compute the similarity scores of the theorems with the `scorer`.
    Save theorems and scores in a file.
    """

    datafile = Path(dataset)
    if not datafile.exists():
        raise Exception(f"Error: {datafile} doesn't exist.")
    savefile = Path(dataset.parent, dataset.stem + "_" + scorer + ".jsonl")

    if savefile.exists():
        print("Scored dataset already here.")
    else:

        print("Making the scored dataset.")

        print("  Download all theorems ...")
        theorems = []
        with open(datafile, "r") as f:
            for line in f:
                theorems.append(json.loads(line))

        print("  Computing the scores ...")
        score_function = scorers[scorer]
        theorems = score_function(theorems)

        print("  Save the dataset ...")
        with open(savefile, "w") as f:
            for theorem in theorems:
                theorem = json.dumps(theorem)
                f.write(theorem + '\n')

        print("  DONE!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Score a dataset of Rocq theorems according to some metric.")
    parser.add_argument("--dataset", type=str, default="math-comp.jsonl", help="The path of the dataset, default is 'math-comp.jsonl'")
    parser.add_argument("--scorer", type=str, default="bm25", help="The scoring algorithm to use, it can be chosen among: " + ",".join(scorers.keys()))
    args = parser.parse_args()
    make(args.dataset, args.scorer)
