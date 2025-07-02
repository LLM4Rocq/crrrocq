# CRRRocq

CRRRocq stands for C(hain of thoughts) R(etrival Assisted Generation) R(ecursive) Rocq (the interactive theorem prover).
In a nutshell, CRRRocq combines chain of thoughts with RAG and tool calling to generate proof in interaction with the Rocq prover.
We focus on the math-comp library, the most advanced mathematics library formalized in Rocq
We train the model to reason using the SSReflect tactic language which is 1) more specialized than vanilla Rocq tactics, 2) less common in the Rocq ecosystem (fewer examples).

## Challenges

- Interface the model with the prover using tool calling
- Break reasoning in multiple subgoals and recursively apply the subgoal
- Few available data (math-comp or proofs using SSReflect)

## Tasks

- [ ] Generate the dataset for the RAG (search tool)
- [ ] Build the RAG
- [ ] Inference pipeline with tool calling
- [ ] Generate the dataset for CoT with tool calling
- [ ] Train the model following the S1 paper (1000 well chosen examples)
- [ ] Test / Benchmarks

## Workflow

### Input

Here is an example of a Rocq theorem from math-comp:

```coq
Lemma size_Poly s : size (Poly s) <= size s.
```

To enable more generalization, this lemma is fed to the LLM in a raw format,
showing only the hypothesis and the goal to prove as follow:

```
<goals>
Goal 0
R  : semiRingType
s  : seq R
|-size (Poly s) <= size s
</goals>
```

### LLM reasoning

Now, the task of the LLM is to write a proof of this goal using a chain of thought
leveraging interaction with the proof assistant and a RAG-based search engine.
Those interactions take the form of tool-calling with several tools available.

Between calls to tools, the model write some informal reasoning inside of `<think>` and `</think>` tags.

Here is an exhaustive list of all the tools available to the model:

### Search

- the LLM search for relevant lemmas that could be used in the proof
- how does it works:
  - the LLM provides an informal description of a theorem enclosed in `<search>` and `</search>` tags;
  - at this point, we stop the inference of the model to obtain the result of the search;
  - a RAG-based search engine matches the LLM's description against a database of descriptions of all available lemmas;
  - the engine returns a list of lemmas matching the description that we enclosed inside of `<result>` and `</result>` tags;
  - the model continues the inference

### Script

- the LLM write some Rocq code
- how does it works:
  - the LLM generates Rocq code in `<script>` and `</script>` tags;
  - at this point, we stop the inference of the model to obtain the report of the script;
  - the script is send to the Rocq type-checker via petanque;
  - the outputs of the type-checker are written inside of `<result>` and `</result>` tags;
  - we provide the new goals to the LLM between `<goals>` and `</goals>` tags;
  - the model continues the inference

### TODO: Definition

- the LLM ask what is the definition of a term
- how does it works:
  - the LLM provides the name of some term he wants to learn about between `<definition>` and `</definition>` tags;
  - at this point, we stop the inference of the model to search for the lemma;
  - using the `Print` keyword of Rocq, we display the information about the lemma;
  - the result is written inside of `<result>` and `</result>` tags;
  - the model continues the inference

### TODO: Have

- the LLM states some intermediate goal he needs to prove
- how does it works:
  - the LLM write the `have` tactic he needs to prove inside of `<have>` and `</have>` tags and a small summary of the proof so far;
  - at this point, we stop the inference of the model to try to prove this intermediate goal;
  - the intermediate goal is given to the model as a new lemma to prove in Rocq, meaning we have a recursive call to the model on a smaller proof;
  - the result of the model is written between `<result>` and `</result>` tags;
  - in case the model succeed to prove the intermediate goal, we provide the new goal to the LLM inside of `<goals>` and `</goals>` tags;
  - the model continues the inference

### Chain of thought (CoT)

For the example given in the input section, the output CoT of the model should look something like this:

``````
<think>
We start with the goal of proving that the size of the polynomial representation of a sequence `s` is less than or equal to the size of `s`. The goal is:

```
R  : semiRingType
s  : seq R
|-size (Poly s) <= size s
```

To progress, we need to understand the structure of `Poly s`. It seems reasonable to break down `Poly s` into a more manageable form. We might need lemmas related to polynomial sequences and equality.
</think>

<search>
Find lemmas related to polynomial sequences and equality.
</search>

<result>
polyseqC:  forall c, c%:P = nseq (c != 0) c

eqxx:  forall (T : eqType) (x : T), x == x
</result>

<think>
The lemmas `polyseqC` and `eqxx` seem useful. `polyseqC` relates a single element polynomial to a sequence, and `eqxx` is a basic equality property. We can use these to rewrite the goal and simplify it.
</think>

<script>
elim: s => [|c s IHs] /=; first by rewrite polyseqC eqxx.
</script>

<result>
The script is correct.
</result>

<goal>
Goal 0
R  : semiRingType
c  : R
s  : seq R
IHs  : size (Poly s) <= size s
|-size (cons_poly c (Poly s)) <= (size s).+1
</goal>

<think>
Now, we need to prove that the size of `cons_poly c (Poly s)` is less than or equal to `(size s).+1`. This involves understanding how `cons_poly` affects the size of the polynomial. We might need lemmas related to the size of polynomials and the structure of `cons_poly`.
</think>

<search>
Find lemmas related to the size of polynomials and the structure of `cons_poly`.
</search>

<result>
size_polyC:  forall c, size c%:P = (c != 0)

ifP:  forall (A : Type) (b : bool) (vT vF : A),
       if_spec b vT vF (b = false) b (if b then vT else vF)

polyseq_cons:  forall c p, cons_poly c p = (if ~~ nilp p then c :: p else c%:P)
</result>

<think>
The lemmas `size_polyC`, `ifP`, and `polyseq_cons` are relevant. `polyseq_cons` shows the structure of `cons_poly`, `size_polyC` gives the size of a single element polynomial, and `ifP` can help with the conditional structure. We can use these to rewrite and simplify the goal.
</think>

<script>
by rewrite polyseq_cons; case: ifP => // _; rewrite size_polyC; case: (~~ _).
</script>

<result>
The script is correct.
</result>

<goal>
No more goals. The proof is finished.
</goal>
``````

## Training

To train the model, we first follow the ["s1: simple test-time scaling"](https://arxiv.org/pdf/2501.19393) paper.
We select 1000 high quality examples from the math-comp library and finetune an openweight model on these examples.


## Benchmarks

- [ ] split of the math-comp dataset (selected for difficulty and diversity)
- [ ] [MiniF2F-Rocq](https://arxiv.org/pdf/2501.19393) a translation of the MiniF2F dataset (highschool exercices) in Rocq
- [ ] [BB4 / BB5](https://github.com/ccz181078/Coq-BB5) recent proofs for the Busy Beaver problem.


