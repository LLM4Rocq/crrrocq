# Dataset generation

A set of steps to generate the final datasets.

* step_0: Remove comments, remove all non source file from mathcomp.
* step_1: Extract all theorems from mathcomp.
* step_2: Extract all have, rewrite them if necessary.
* step_3: Extract a diverse set of theorems using BM25.
* step_4: Evaluate all theorems (goals, dependencies, etc.) from step 3.

## Usage

To avoid issues with file collisions/corruption, debugging, and to have easily adaptable code, we implement a step-by-step pipeline.
Each step depends on the output of the previous step, input/output can be customized.

### First step

To preprocress mathcomp (clean comment, keep source file only etc.) replace $MATHCOMP_PATH by a directory containing a copy of mathcomp (e.g. [this fork](https://github.com/theostos/math-comp)) (default to export/mathcomp).

```console
python -m src.steps.step_0.exec --input $MATHCOMP_PATH
```

(By default, output is set to "export/outputs/steps/step_0")

### Second step

Extract all theorems from mathcomp.

```console
python -m src.steps.step_1.exec
```

### Third step

Extract all have, rewrite them if necessary.

```console
python -m src.steps.step_2.exec --max-workers 4
```

To extract "have" using 4 workers.

### Fourth Step

Extract a diverse set of theorems using BM25.

```console
python -m src.steps.step_3.exec --k_have 500 --k_wo_have 500
```
To extract a diverse set of 500 theorems with "have" statements, and 500 without "have" statements.

### Fifth Step

Evaluate all theorems (goals, dependencies, etc.), and annotate theorems with docstrings given in a dictionary file. A json, with the following format:

- fully qualified name
    + name
    + kind
    + docstring
    + fullname

An example
- "export.output.steps.step_0.fingroup.action.act_morph":
    + "name": "act_morph",
    + "kind": "Definition",
    + "docstring": "The property that for a function to, applying to to an element x and the product of two group elements a and b is the same as applying to to x and a, and then applying to again to the result and b. This expresses the composition law required for a group action.",
    + "fullname": "Definition act_morph to x := forall a b, to x (a * b) = to (to x a) b."

```console
python -m src.steps.step_4.exec --dictionary=export/docstrings/dictionary.json --max-workers 4
```

To evaluate "have" using 4 workers.