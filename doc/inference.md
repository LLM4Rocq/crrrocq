# Quickstart: Evaluation Pipeline

## Installation

TO DO

## Running Inference

Launch the pipeline with:

```bash
./config/inference/start_all.sh
```

This will start sequentially:

* **sglang**
* **retrieval/pet-server**
* **agents**

## Output of Agents

Agent logs are saved by default in the `agent_logs` directory (see the default parameter in `argparse` within `script/inference.py`).

* If a log name starts with `SUCCESS`, it means the proof was successful.
* If it starts with `FAIL`, the proof attempt failed.

Example: Log (failed to connect to server)

```json
{
    "blocks": [],
    "logs": [],
    "status": "fail",
    "message": "(500, '<html>\n  <head>\n    <title>Internal Server Error</title>\n  </head>\n  <body>\n    <h1><p>Internal Server Error</p></h1>\n    \n  </body>\n</html>\n')"
}
```

Example: Log (detailed failure)

```json
{
    "blocks": [
        {
            "kind": "think",
            "content": "I need to prove that for any group morphism f and set A, the image of the normalizer of A is contained in the normalizer of the image of A: `f @* 'N(A) \subset 'N(f @* A)`..."
        }
        // ...
    ],
    "logs": [
        {
            "status": "fail",
            "message": "Error description",
            "context": "Previous block before failure",
            "content": "Block that provoked the failure"
        }
        // ...
    ],
    "status": "fail",
    "message": "Max retries reached for script."
}
```

* The `blocks` field contains the sequence of model outputs for this proof attempt.
* The `logs` field records the history of errors and context during the proof search.

## Changing the Evaluation Set

To evaluate on a custom set:

1. Edit the `--evaluation-file` parameter in `script/inference.py` (default: `/lustre/fsn1/projects/rech/tdm/commun/dataset/new_evaluation.json`).
2. Make sure the referenced file contains a list or dict of theorem names, matching entries in your script server config (`config/server/script/config.yaml`, key: `thms_paths`).

### Example: Evaluation Set

* `new_evaluation.json`:

  ```json
  ["foo.test"]
  ```
* `filename.json`:

  ```json
  {
    "foo.test": {
      "position": { "line": 169, "character": 0 },
      "filepath": "/lustre/fsn1/projects/rech/tdm/commun/mathcomp/fingroup/action.v",
      "statement": "Lemma is_total_action : is_action setT to."
    }
  }
  ```

## Configuration

* **Agents parameters**
  `config/inference/agent.slurm`
  (e.g. pass@k, log dir, max workers)
  argparse of inference/script.py

* **Model and inference parameters:**
  `config/inference/inference.yaml`
  (e.g., model path, prompt path, generation settings)

* **Retrieval server:**
  `config/server/retrieval/config.yaml`
  (e.g., cache path, docstrings, embedding model)

* **Script server:**
  `config/server/script/config.yaml`
  (e.g., number of servers, theorem paths)

* **SLURM / node configs:**
  `config/inference/*.slurm`

### Inference: `config/inference/inference.yaml`

```yaml
llm_kind: "openai_instruct"
prompt_path: "export/dataset/prompt.json"
llm_config:
  model_name: "/lustre/fsn1/projects/rech/tdm/commun/models/crrrocq_compress/"
  api_key: "None"
  generation_parameters:
    temperature: 0.7
    max_tokens: 2048
    stop:
      - "</search>"
      - "</script>"
      - "</have>"
tools:
  have: {}
  search: {}
  script: {}
max_retry:
  search: 2
  have: 32
  script: 32
max_depth: 128
```

### Retrieval: `config/server/retrieval/config.yaml`

```yaml
cache_path: "/lustre/fsn1/projects/rech/tdm/commun/cache/"
docstrings_path: "/lustre/fsn1/projects/rech/tdm/commun/dataset/docstrings.json"
model_name: "/lustre/fsn1/projects/rech/tdm/commun/hf_home/hub/models--Qwen--Qwen3-Embedding-4B/snapshots/5cf2132abc99cad020ac570b19d031efec650f2b"
```

* `cache_path`: Where to store and retrieve docstrings embedding
* `docstrings_path`: JSON containing all mathcomp docstrings
* `model_name`: Model used to compute embeddings

Expected docstrings format ("docstrings_path")

```json
"mathcomp.fingroup.action.act_morph": {
  "name": "act_morph",
  "kind": "Definition",
  "docstring": "The property that for a function to, applying to to an element x and the product of two group elements a and b is the same as applying to to x and a, and then applying to again to the result and b. This expresses the composition law required for a group action.",
  "fullname": "Definition act_morph to x := forall a b, to x (a * b) = to (to x a) b.",
  "start_line": 20,
  "end_line": 21,
  "parent": "mathcomp.fingroup.action"
}
```

### Script `config/server/script/config.yaml`

```yaml
num_pet_server: 4
pet_server_start_port: 8765
thm_paths: "/lustre/fsn1/projects/rech/tdm/commun/dataset/filename.json"
```

* `thms_paths`: JSON mapping fully qualified theorem names to filepaths and positions

Expected theorems path format ("thm_paths")

```json
"mathcomp.fingroup.action.is_total_action": {
  "position": {
    "line": 169,
    "character": 0
  },
  "filepath": "/lustre/fsn1/projects/rech/tdm/commun/mathcomp/fingroup/action.v",
  "statement": "Lemma is_total_action : is_action setT to."
}
```
