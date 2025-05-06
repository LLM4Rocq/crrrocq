Your task is to simulate realistic training data for a model designed to perform mathematical proofs in the MathComp style, based on an already known proof, and the corresponding sequence of intermediate goals and tactics. Your simulation will create structured "reasoning blocks," reflecting genuine, incremental reasoning aligned with the provided proof sequence. Each block of reasoning should realistically employ one or more of the following tools available to the model:

- Execute a block of proof script: to progress towards or modify the current goal.
- Perform a search (IR): to retrieve helpful lemmas or theorems from a corpus based on informal descriptions.
- Define and prove an intermediate lemma: if necessary to simplify the current goal or support the reasoning.

For each reasoning block, adhere strictly to the following structured format:

<think>
[Explicitly describe your inner reasoning, capturing uncertainty and incremental thought processes. Discuss your analysis of the current goal, potential approaches, the reasoning behind considering certain lemmas or script executions, or the rationale behind defining an intermediate lemma. Simulate the discovery ot the next tactics.
PRETEND THAT YOU DO NOT KNOW THE NEXT TACTIC OR THE COMMENT. Do not copy the tactics or the surrounding comment.]
</think>

<search>
[Informal query to find a lemma from the corpus. Write what you would type if you didn't know the name of the lemma. To guide you we added comments (* SEARCH ... *) listing the lemmas used in the next tactics. Insert a search block to retrieve these lemma for each SEARCH comment.]
</search>

<result>
[Lemma(s) retrieved from the search engine.]
</result>

<think>
[If applicable; an additional reasoning step to explain how you can use these Lemmas in a script or a tactic.]
</think>

<script>
[If applicable: exact script instruction applied (e.g., Coq/SSReflect tactic).]
</script>

<result>
[New context and goal(s) as given by the environment — these are not to be predicted, only output what the environment would reveal after the script is run.]
</result>

Repeat this structured approach clearly for each subsequent tactic, explicitly simulating the reasoning process based on the provided goal and next known tactic.

Guidelines:

- Context for each reasoning block: clearly consider the provided theorem statement, the current goal, the known tactic sequence, and previous steps already performed.
- Detailed reasoning: ensure your inner thought process is detailed, realistic, and incremental. Simulate genuine exploration, including dead-ends, uncertainties, and corrections in thinking if applicable.
- Tool usage justification: clearly justify why you're choosing a particular tool (script execution, search, or lemma definition) based explicitly on the provided next tactic step.
- Search specifics: when using search, formulate an informal query clearly reflecting your uncertainty or the type of result you're seeking.
- Intermediate lemmas: if defining a lemma, clearly explain why it simplifies or helps your reasoning process.
- Realistic constraints: simulate realistic limitations — acknowledge explicitly when certain lemmas might not be available, when searches fail, or when script executions lead to unexpected results.
- This structured simulation is crucial as it will serve as the training dataset for a model learning incremental, realistic proof reasoning using MathComp.

Here are a few examples.

Example 1.
Input.

<goals>
Goal 0
F  : fieldType
L  : splittingFieldType F
E  : {subfield L}
A  : {set gal_of E}
a  : L
|-a \in fixedField A -> a \in E /\ (forall x : gal_of E, x \in A -> x a = a)
</goals>

<tactic>
(* SEARCH fixedFieldP memv_capP *)
by move=> fixAa; have [Ea _] := memv_capP fixAa; have:= fixedFieldP Ea fixAa.
</tactics>

Expected output.

<think>
We start with the goal of proving that if an element \( a \) is in the fixed field of a set \( A \) of Galois automorphisms, then \( a \) is in \( E \) and is fixed by all elements of \( A \).

The goal is:
\[ a \in \text{fixedField } A \rightarrow a \in E \land (\forall x : \text{gal\_of } E, x \in A \rightarrow x \, a = a) \]

To approach this, we need to break down the implication and understand the components involved. The statement involves membership in the fixed field and properties of Galois automorphisms.

We should look for lemmas or theorems that relate to fixed fields and membership properties. Specifically, we need something that can help us rewrite or simplify the membership condition \( a \in \text{fixedField } A \).
</think>

<search>
Find lemmas related to the fixed field and membership properties in vector spaces.
</search>

<result>
fixedFieldP:  forall E (A : {set gal_of E}) (a : L),
       a \in E ->
       reflect (forall x : gal_of E, x \in A -> x a = a) (a \in fixedField A)

memv_capP:  reflect (?w \in ?U /\ ?w \in ?V) (?w \in (?U :&: ?V)%VS)
where
?K : [F : fieldType  L : splittingFieldType F |- fieldType]
?vT : [F : fieldType  L : splittingFieldType F |- vectType ?K]
?w : [F : fieldType  L : splittingFieldType F |- Vector.sort ?vT]
?U : [F : fieldType  L : splittingFieldType F |- {vspace ?vT}]
?V : [F : fieldType  L : splittingFieldType F |- {vspace ?vT}]
</result>

<think>
The search results provide two useful lemmas:

1. `fixedFieldP`: This lemma states that for any element \( a \) in \( E \), the condition \( a \in \text{fixedField } A \) is equivalent to \( a \) being fixed by all elements of \( A \). This directly relates to our goal and can help us rewrite the membership condition.

2. `memv_capP`: This lemma deals with membership in the intersection of vector spaces. It might be useful if we need to handle membership in multiple sets simultaneously.

Given these lemmas, we can start by applying `memv_capP` to handle the membership condition \( a \in E \land (\forall x : \text{gal\_of } E, x \in A \rightarrow x \, a = a) \). Then, we can use `fixedFieldP` to rewrite the fixed field condition.
</think>

<script>
by move=> fixAa; have [Ea _] := memv_capP fixAa; have:= fixedFieldP Ea fixAa.
</script>

<result> 
Proof finished.
</result> 

Example 2.

Input.

<goals>
Goal 0
R  : semiRingType
s  : seq R
|-size (Poly s) <= size s
</goals>

SEARCH polyseqC eqxx

<result>
polyseqC:  forall c, c%:P = nseq (c != 0) c

eqxx:  forall (T : eqType) (x : T), x == x

</result>
<tactic>
elim: s => [|c s IHs] /=; first by rewrite polyseqC eqxx.
</tactics>

<goals>
Goal 0
R  : semiRingType
c  : R
s  : seq R
IHs  : size (Poly s) <= size s
|-size (cons_poly c (Poly s)) <= (size s).+1
</goals>

SEARCH size_polyC ifP polyseq_cons

<result>
size_polyC:  forall c, size c%:P = (c != 0)

ifP:  forall (A : Type) (b : bool) (vT vF : A),
       if_spec b vT vF (b = false) b (if b then vT else vF)

polyseq_cons:  forall c p, cons_poly c p = (if ~~ nilp p then c :: p else c%:P)

</result>
<tactic>
by rewrite polyseq_cons; case: ifP => // _; rewrite size_polyC; case: (~~ _).
</tactics>


Expected output.

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
Goal 0
R  : semiRingType
c  : R
s  : seq R
IHs  : size (Poly s) <= size s
|-size (cons_poly c (Poly s)) <= (size s).+1
</result>

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
Proof finished.
</result> 