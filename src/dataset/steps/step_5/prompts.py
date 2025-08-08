code_explanation_prompt = """**Task**: Explain Rocq/Coq ssreflect tactics with precise detail.

**Context**: You will be provided with a tactic as input. To help you understand the context the list of hypotheses and the goal will be given. You will also be provided with type information for all dependencies (lemmas, definitions, etc.) used in the tactic, along with descriptions of some dependencies to help explain their purpose and behavior.

**Format**: Provide exactly three sections:

1. **Breaking it down**: List each symbol/component with brief explanations
2. **What happens**: Describe the step-by-step execution and transformations
3. **Summary**: Summarize the "What happens" section

**Requirements**:
- Be concise but comprehensive - cover every symbol and detail
- Target audience knows nothing about ssreflect syntax
- Focus on tactical mechanics (what each symbol does, how patterns work, rewrite directions, etc.)
- No introductory fluff or conclusions

**Example input**:
Goal:
b1, b2 : bool
|- b1 /\\ b2 = b1 && b2

Tactic:
rewrite -{{1}}[b1 && b2]andP.

Dependencies:
andP : forall {{b1 b2 : bool}}, reflect (b1 /\\ b2) (b1 && b2)

**Expected output**:
## Breaking it down:
- **`rewrite`**: ssreflect tactic to apply rewrite rules
- **`-`**: The "reverse direction" flag - applies the rewrite rule from right-to-left
- **`{{1}}`**: Occurrence selector - only rewrite the **first** occurrence
- **`[b1 && b2]`**: Pattern selector - only rewrite instances that match this specific pattern
- **`andP`**: The reflection lemma `reflect (b1 /\\ b2) (b1 && b2)`

## What happens:
1. **Finds the pattern**: Looks for expressions matching `b1 && b2` (boolean conjunction)
2. **Applies reverse rewrite**: Since `andP` normally goes `(b1 /\\ b2) ↔ (b1 && b2)`, the `-` makes it go backwards: `(b1 && b2) → (b1 /\\ b2)`
3. **Only first occurrence**: The `{{1}}` means if there are multiple `b1 && b2` expressions, only rewrite the first one
4. **Converts boolean to logic**: Changes the boolean conjunction `b1 && b2` into the logical conjunction `b1 /\\ b2`

## Summary:
Converts the first occurrence of boolean conjunction `b1 && b2` to logical conjunction `b1 /\\ b2` using the andP reflection lemma in reverse.

**Special case**: Tactics framed by `(*<have>*)` and `(*</have>*)` tags are special - the proof of the goal they introduce is hidden and replaced by `(*proof*)`. For such have tactics, the "What happens" section should NOT MENTION THE SUBGOAL INTRODUCED, as it is directly handled by the hidden proof. Only mention how the main goal is changed.

Ready? Here is the input:
{input}
"""

proof_explanation_prompt = """**Task**: Translate Rocq/Coq mathcomp proofs to natural language that mimics mathematical reasoning.

**Context**: You will receive a formal proof from the mathcomp Rocq library in structured format. The proof is broken down tactic by tactic with supporting information. Your goal is to reveal the mathematician's thought process - the strategic reasoning behind each step, not just what each tactic does mechanically.

**Input Format**:
- **`<statement>` and `</statement>` tags**: Contains the formal lemma statement
- **`<initial_goal>` and `</initial_goal>` tags**: Shows the initial proof goal
- **`<proof>` and `</proof>` tags**: Contains the complete proof broken down tactic by tactic. Each tactic is framed by `<tactic>` and `</tactic>` tags and contains:
    - **`<code>` and `</code>` tags**: Contains the tactic code
    - **`<dependencies>` and `</dependencies>` tags**: The lemmas, theorems, definitions, etc. that appear in the tactic (if present)
    - **`<summary>` and `</summary>` tags**: A summary of what the tactic does
    - **`<goal_diff>` and `</goal_diff>` tags**: Shows how the proof state changes after the application of the tactic

**Output Format**: Provide exactly two sections:

1. **Statement**: Explain what the lemma claims mathematically
2. **Proof**: Present the mathematical reasoning process, linking concepts to formal elements

**Requirements**:
- **No tactic-by-tactic translation** - weave tactics into coherent mathematical narrative
- **Mimic the prover's reasoning** - show why each step was chosen and how it advances the strategy
- **Link reasoning to code** - reference specific tactics parts and dependencies when explaining corresponding mathematical ideas
- **Show strategic thinking** - distinguish between steps that advance the proof vs. prepare groundwork
- **Reveal the overall plan** - demonstrate how early moves enable later applications
- **Connect formal to mathematical** - show how dependencies provide the mathematical tools needed

**Focus**: The reader should understand the mathematical insight and strategic thinking, while seeing how it corresponds to the formal proof structure. Emphasize the logical flow and preparation steps that make the proof work.

Ready? Here is the input:
{input}
"""

CoT_creation_prompt = """# Chain of Thought Generation Task

## Introduction

We are a team of researchers specializing in machine learning, particularly LLMs, and formal methods, especially the Coq proof assistant. Our goal is to improve LLM performance in generating Coq proofs. We have an idea to achieve this goal: ensure that the chains of thought (CoT) generated by our LLMs interact extensively with the interactive Coq prover. For this, we want LLMs to be able to call various 'tools' in their CoT in the following manner:

```
...
<think> some thinking part from the LLM </think>
<search> searching for some pre-existing theorems </search>
<result> the results of the search </result>
<think> another thinking part </think>
<script> some attempt at writing some Coq code </script>
<result> the results of the script </result>
<have> some attempt at doing a have tactic </have>
<result> the results of attempt at writing a have tactic </result>
...
```

We will generate a dataset of CoT examples starting from theorems already proven in math-comp, the largest mathematics library in Coq. With this dataset, we will train a model using supervised fine-tuning that will know how to use tools in its CoTs.

## Your Task

You are part of the team, and your role is to generate these CoTs. You are particularly skilled in Coq, so this work is perfect for you! Since you already have the proofs of the theorems, you simply need to look at the proof, simulate the reasoning that went through the mind of the person who wrote it, and write this reasoning in the expected format: with tags delimiting tool calls. Since the results of the calls are not to be generated by the LLMs, you don't need to write the `<result> ... </result>` parts; they will be added later by another team member.

To help you simulate the CoTs and know when to simulate tool calls, the proofs of the theorems will be given to you in a particular format:
- **theorem statement**: the Coq statement of the theorem;
- **statement description**: an informal language description of the theorem;
- **initial goal**: the initial goal, a list of hypotheses and the Coq goal;
- **proof decomposition**: the proof is given as a sequence of tactics separated by points, for each tactics you will have:
  - **code**: the code of the tactic
  - **dependencies**: if any, the lemmas, theorems, definitions, etc. that appears in the tactic. For each dependency we give its type and a short description if available
  - **detail**: the detail of the code of the tactic
  - **goal difference**: how applying the tactic changes the goal
- **proof description**: a description of the proof in natural language. The reasoning in the description doesn't follow lineary the sequence of tactics of the Coq code, its reasoning flow is more logical and should be a guide for the reasoning flow of your simulation.

## Available Tools Overview

- **Think block**: classic reasoning phase of an LLM, default mode that doesn't correspond to calling any tools.
- **Search block**: allows the LLM to understand the environment it's in. In this block, the LLM writes a natural language description of a theorem that might be useful to it, and the result is a list of existing theorems provided by a search algorithm comparing text embeddings
- **Script block**: the LLM proposes some Coq code that is type-checked by the tool. If the code type-checks, the result is made of the new goal; otherwise, we return the error from Coq.
- **Have block**: enables the LLM to delegate the intermediary proof needed by a have tactic. As for a script block, the input is some Coq code that should always be a have tactic introducing an intermediary goal. Still in the same way as a script block, the code is type-checked and if it fails, we return the error from Coq. Otherwise, the result indicates if the tool succeeded to prove the intermediate goal by providing the new goal. If it doesn't, the result simply tells it failed.

In the end, the final proof of the LLM will be the concatenation of all valid script blocks and have blocks.

### Simulation

When should you write the different blocks?

**Think block**: whenever reasoning in informal language.

**Search block**: whenever the LLM needs to search for a theorem.
To simulate this block, use the dependencies of a tactic given in the input: you know that the LLM must search for these theorems to write the tactic. So for each theorem in the dependencies, you can write a search block resulting in this theorem. To properly react to the result, keep in mind that it contains several theorems and only one that would interests the LLM to continue its proof. After the search block, the choice of that particular theorem over the others must be justified.

**Script block**: whenever the LLM is expected to propose code, for each tactic of the input.
Coq code writing is difficult so we want LLM to proceed carefully when proposing some code. To properly train the LLM, precede the script block by a preparation of the script. In this preparation, come up with the different parts of the code before merging them all together in the script block. Each symbol, operator, modifier, tactic keywords and lemmas applications must stem from a need previously identified and explained to provide the LLM with a thorough and precise workflow. This is a hard task for you, hopefully the detail of each tactic provided in the input contains all the information you need to break down exactly what each part of the tactic does. Use the given details EXTENSIVELY, most of what they present should be mentioned in the CoT.
Additionally, given the goal differences in input, you can properly simulate the reaction to the result of a script block.

**Have block**: whenever the LLM should write a have tactic introducing intermediary goals.
But not all have tactics do so, we have selected such have tactics by framing them with tags `(*<have>*)` and `(*</have>*)` in the code. Moreover, the proof of the intermediary goal is hidden and replaced by `(*proof*)` because you don't need to know it.
Such have tactics can be seen as intermediary lemmas whose proof is delegated. So it's rare for someone to write an intermediary lemma without ensuring that an already existing lemma doesn't do what that person wants. From this perspective, a have block must be preceded by a failed search block to properly simulate its necessity. By failed search block, we mean a search block that didn't resulted in interesting lemmas. And because an interesting lemma would do exactly what the have tactic does, the failed search block's query should be a description of the have tactic's statement.

**Remarks**:
- Have blocks are very similar to script blocks in the sense that they contains code. So precede all have blocks by a detailed preparation of the code using the details of the have tactic and use the goal difference to react accordingly to results of have blocks.
- Some have tactics written in have blocks contain dependencies, write dedicated search blocks for them.
- Other tactics introduce hypotheses (like `suff` or `wlog`), to justify such tactics you can do the same staging as for have blocks with a failed search block. However, you should conclude with a script block since have blocks are reserved for have tactics.

## Example

**Expected input**:
<statement>
Lemma eqp_modpr d p q : p %= q -> (d %% p) %= (d %% q).
</statement>

<statement_description>
This lemma establishes that polynomial remainder operation respects associateness: if two polynomials p and q are associates (differ only by multiplication by nonzero constants), then for any polynomial d, the remainders d %% p and d %% q are also associates.
</statement_description>

<initial_goal>
F  : fieldType
d, p, q  : {{poly F}}
|-p %= q -> d %% p %= d %% q
</initial goal>

<proof>

<tactic>
<code>
case/eqpP=> [[c1 c2]] /andP [c1n0 c2n0 e].
</code>
<dependencies>
eqpP : forall [R : idomainType] (m n : {{poly R}}),
  reflect
    (exists2 c12 : R * R,
       (c12.1 != 0) && (c12.2 != 0) & c12.1 *: m = c12.2 *: n)
    (m %= n)
This lemma provides a reflection between the boolean predicate testing whether two polynomials are associates and the proposition that there exists a nonzero scalar c such that scaling the first polynomial by c yields the second polynomial.

andP : forall {{b1 b2 : bool}}, reflect (b1 /\\ b2) (b1 && b2)
</dependencies>
<detail>
- **`case`**: ssreflect tactic that performs case analysis/elimination on the top of the goal
- **`/eqpP`**: View hint - applies the `eqpP` reflection lemma to convert boolean `p %= q` to the logical proposition about existence of scaling factors
- **`=>`**: Introduction arrow - introduces the resulting hypothesis into the context
- **`[[c1 c2]]`**: Nested destructuring pattern - extracts the pair `c12 : R * R` from the existential, binding `c12.1` to `c1` and `c12.2` to `c2`
- **`/andP`**: Another view hint - applies the `andP` reflection lemma to convert boolean conjunction to logical conjunction
- **`[c1n0 c2n0 e]`**: Destructuring pattern for the conjunction - splits `(c1 != 0) && (c2 != 0) & c1 *: p = c2 *: q` into three parts: `c1n0 : c1 != 0`, `c2n0 : c2 != 0`, and `e : c1 *: p = c2 *: q`
</detail>
<goal_diff>
Goals modified:

The goal 0 is changed:
Hypotheses added:
c1 : F
c2 : F
c1n0 : (c1, c2).1 != 0
c2n0 : (c1, c2).2 != 0
e : (c1, c2).1 *: p = (c1, c2).2 *: q

The goal changed to:
|-d %% p %= d %% q
</goal_diff>
</tactic>

<tactic>
<code>
(*<have>*) have -> : p = (c1^-1 * c2) *: q. (*proof*)  (*</have>*)
</code>
<detail>
- **`have`**: ssreflect tactic to introduce a new hypothesis
- **`->`**: Rewrite arrow - immediately applies the new hypothesis as a left-to-right rewrite rule
- **`:`**: Separates the optional pattern/name from the statement to prove
- **`p = (c1^-1 * c2) *: q`**: The equality statement being proven and immediately applied
- **`(*proof*)`**: Hidden proof that establishes the equality
</detail>
<goal_diff>
Goals modified:

The goal 0 is changed:
The goal changed to:
|-d %% ((c1^-1 * c2) *: q) %= d %% q
</goal_diff>
</tactic>

<tactic>
<code>
by rewrite modpZr ?eqpxx // mulf_eq0 negb_or invr_eq0 c1n0.
</code>
<dependencies>
modpZr : forall [c : F] p d, c != 0 -> p %% (c *: d) = p %% d
For any nonzero scalar c and polynomials p and d, dividing p by c·d yields the same remainder as dividing p by d.

eqpxx : forall [R : idomainType], reflexive (eqp (R:=R))
The boolean association relation on polynomials is reflexive.

mulf_eq0 : forall [R : idomainType] (x y : R), (x * y == 0) = (x == 0) || (y == 0)
(*The lemma mulf_eq0 states that in a field, the product of two elements equals zero if and only if at least one of the two elements is zero.*)

negb_or : forall a b : bool, ~~ (a || b) = ~~ a && ~~ b

invr_eq0 : forall [R : unitRingType] (x : R), (x^-1 == 0) = (x == 0)
The inverse of an element equals zero exactly when the element itself equals zero.
</dependencies>
<detail>
- **`by`**: Proof termination tactic - completes the proof using the following tactics
- **`rewrite`**: ssreflect tactic to apply rewrite rules
- **`modpZr`**: Lemma stating `c != 0 -> p %% (c *: d) = p %% d` (remainder unchanged when scaling divisor)
- **`?`**: Optional application operator - tries to apply the next tactic, continues if it fails
- **`eqpxx`**: Reflexivity lemma for polynomial equivalence relation `eqp`
- **`//`**: Trivial goal solver - attempts to solve goals by computation/assumption lookup
- **`mulf_eq0`**: Lemma stating `(x * y == 0) = (x == 0) || (y == 0)` in integral domains
- **`negb_or`**: Boolean negation distribution over disjunction: `~~ (a || b) = ~~ a && ~~ b`
- **`invr_eq0`**: Lemma stating `(x^-1 == 0) = (x == 0)` for inverses
- **`c1n0`**: Hypothesis that `(c1, c2).1 != 0`
</detail>
<goal_diff>
1 goal has been removed.
There is no goal remaining, the proof is finished.
</goal_diff>
</tactic>

</proof>

<proof_description>
The proof strategy centers on leveraging the fundamental property that scaling a divisor by a nonzero constant doesn't affect the remainder in polynomial division. The key insight is to transform the associate relationship into an explicit scaling relationship that can be directly applied to the remainder operation.

We begin by unpacking the hypothesis `p %= q` using `eqpP`, which reveals the concrete meaning of associateness: there exist nonzero scalars c₁ and c₂ such that c₁ · p = c₂ · q. The `case/eqpP=> [[c1 c2]] /andP [c1n0 c2n0 e]` tactic extracts these witnesses along with the crucial nonzero conditions and the scaling equation.

The mathematical crux comes in the next step, where we algebraically manipulate the equation c₁ · p = c₂ · q to isolate p. Since c₁ ≠ 0, we can multiply both sides by c₁⁻¹ to obtain p = (c₁⁻¹ · c₂) · q. This rewriting transforms our goal from proving `d %% p %= d %% q` to the more manageable `d %% ((c₁⁻¹ · c₂) · q) %= d %% q`.

The final step exploits the key property `modpZr`, which states that for any nonzero scalar c, we have `p %% (c · d) = p %% d`. To apply this lemma, we must verify that our scaling factor c₁⁻¹ · c₂ is indeed nonzero. This verification unfolds through a chain of logical equivalences: the product is nonzero if and only if both factors are nonzero (`mulf_eq0`), the inverse c₁⁻¹ is nonzero exactly when c₁ is nonzero (`invr_eq0`), and we already established both c₁ ≠ 0 and c₂ ≠ 0 from our initial case analysis.

With the nonzero condition confirmed, `modpZr` immediately gives us `d %% ((c₁⁻¹ · c₂) · q) = d %% q`, and since equality implies associateness (`eqpxx` provides reflexivity), the proof concludes.

This proof elegantly demonstrates how associateness propagates through polynomial operations by reducing the abstract notion of "differing by units" to concrete scalar manipulations that respect the algebraic structure of polynomial division.
</proof_description>

**Expected output**:
<think>
I need to prove that polynomial remainder operation respects associateness: if two polynomials p and q are associates (they differ only by multiplication by nonzero constants), then for any polynomial d, the remainders d %% p and d %% q are also associates.

The statement is: `p %= q -> (d %% p) %= (d %% q)`

This seems intuitive - if p and q are "essentially the same" up to scaling, then dividing any polynomial d by either should give "essentially the same" remainder. But I need to make this precise.

The key question is: what does it mean for two polynomials to be associates? The notation `p %= q` suggests some equivalence relation, but I need to understand its concrete meaning to work with it algebraically.
</think>

<search>
A lemma about associate relation for polynomials.
</search>

<think>
Perfect! The eqpP lemma is exactly what I was looking for. It provides a reflection between the boolean predicate `m %= n` and a concrete logical proposition: there exist nonzero scalars c1, c2 such that `c1 *: m = c2 *: n`.

This is much more workable than the abstract notion of "associates." It tells me that if p %= q, then there are concrete witnesses - nonzero constants that relate p and q through scaling.

Now I'm wondering: there might be a lemma about how scaling the divisor affects the remainder...
</think>

<search>
A lemma about polynomial remainder when the divisor is scaled by a nonzero constant.
</search>

<think>
Mmh, among all the lemmas, modpZr seems to be the most promising. It states that for nonzero c: `p %% (c *: d) = p %% d`. This is exactly the key insight I need - scaling the divisor by a nonzero constant doesn't change the remainder!

But wait, modpZr doesn't directly solve my goal. I have `p %= q`, which means there exist nonzero c1, c2 with `c1 *: p = c2 *: q`. But I need the goal to be of the form `p %% (c *: d) = p %% d`.

Let me think... if `c1 *: p = c2 *: q`, then `p = (c1^-1 * c2) *: q` (since c1 is nonzero, I can multiply both sides by c1^-1). If I can establish this equality and substitute it into my goal, then I'd have `d %% ((c1^-1 * c2) *: q) %= d %% q`, and modpZr could help if (c1^-1 * c2) is nonzero which is the case because c1 and c2 are nonzero.

So my strategy is:
1. Apply eqpP to extract the scaling witnesses c1, c2 and their properties
2. Establish the equality `p = (c1^-1 * c2) *: q`
3. Rewrite the goal using this equality
4. Apply modpZr
5. Use reflexivity of the associate relation

Let me start implementing this plan...

The first step is to apply eqpP to my hypothesis `p %= q` to extract the concrete scaling relationship.

Let me think carefully about what eqpP does. The lemma states:
```
eqpP : forall [R : idomainType] (m n : {{poly R}}),
  reflect
    (exists2 c12 : R * R,
       (c12.1 != 0) && (c12.2 != 0) & c12.1 *: m = c12.2 *: n)
    (m %= n)
```

So applying eqpP to `p %= q` will transform this boolean predicate into a logical proposition about the existence of a pair c12 such that:
1. `c12.1 != 0` (the first component is nonzero)
2. `c12.2 != 0` (the second component is nonzero)
3. `c12.1 *: p = c12.2 *: q` (the scaling equation)

The first two conditions are combined in a boolean conjunction `(c12.1 != 0) && (c12.2 != 0)`.

Now, my ultimate goal is to manipulate the equation `c12.1 *: p = c12.2 *: q` to isolate p. Since c12.1 is nonzero, I can multiply both sides by c12.1^-1:
- `c12.1 *: p = c12.2 *: q`
- `c12.1^-1 *: (c12.1 *: p) = c12.1^-1 *: (c12.2 *: q)`
- `(c12.1^-1 * c12.1) *: p = (c12.1^-1 * c12.2) *: q`
- `1 *: p = (c12.1^-1 * c12.2) *: q`
- `p = (c12.1^-1 * c12.2) *: q`

But to perform this manipulation, I need access to the individual scalars c12.1 and c12.2, not just the abstract pair c12.

Since eqpP is a reflection lemma (it provides a `reflect` statement), I can use it in a `case` tactic with SSReflect's view syntax. The pattern `case/eqpP` will:
1. Apply the eqpP reflection to convert `p %= q` to the existential proposition
2. Perform case analysis on the resulting existential

But I need to be careful about how I handle the introduction and destructuring. Let me think step by step:

After `case/eqpP`, I'll have the existential `forall c12 : R * R, ...` in my context, and I need to introduce it. The `=>` arrow allows me to introduce hypotheses.

Since c12 is a pair, I want to immediately destructure it to get its components, lets say c1 and c2. In SSReflect, I can use nested destructuring patterns that I indicate by framing it inside of bracket `[...]`. The destructing pattern for a pair is `[c1 c2]`, that will bind c12.1 to c1 and c12.2 to c2.

So `case/eqpP => [[c1 c2]]` will:
1. Apply eqpP to convert the boolean `p %= q` to the logical existential
2. Perform case analysis on the existential
3. Introduce the pair witness and immediately destructure it as c1, c2

This gives me direct access to the two scalars as separate variables c1 and c2.

But now I have a problem. After this step, I still need to introduce the remaining hypotheses:
- The nonzero conditions: `(c1 != 0) && (c2 != 0)`
- The scaling equation: `c1 *: p = c2 *: q`

The issue is that the nonzero conditions are packaged as a boolean conjunction `(c1 != 0) && (c2 != 0)`. If I just continue with `case/eqpP => [[c1 c2]] [nz_cond e]`, then nz_cond will be the entire boolean expression `(c1 != 0) && (c2 != 0)`, not the individual conditions.

This is problematic because in my next step, I need to use the fact that c1 is nonzero specifically to justify multiplying by c1^-1. Having the boolean conjunction doesn't directly give me `c1 != 0` as a separate hypothesis - I'd need to extract it from the conjunction later.

It would be much cleaner if I could split this boolean conjunction into two separate logical propositions: `c1 != 0` and `c2 != 0`. Then I could introduce them as separate hypotheses right away.

Is there a way to convert a boolean conjunction to a logical conjunction? This seems like something that should exist in the boolean reflection library...
</think>

<search>
A reflection betwee a boolean conjunction and a logical conjunction.
</search>

<think>
Perfect! andP is exactly what I need. It reflects boolean conjunction `b1 && b2` to logical conjunction `b1 /\\ b2`. This will let me split the nonzero conditions into separate hypotheses.

Now, the key insight is that andP is also a view lemma, just like eqpP. This means I can chain view applications in SSReflect! I can use the syntax `/andP` to apply this reflection in the same tactic where I'm already using `/eqpP`.

Appending `/andP` to the tactic will convert the boolean conjunction to a logical conjunction. Then, I can use a destructing pattern for logical conjunction to introduce all the different hypotheses `[c1n0 c2n0 e]`. This should give me the new hypotheses: c1n0 (c1 != 0), c2n0 (c2 != 0), and e (c1 *: p = c2 *: q).

This gives me exactly the components I need for the following algebraic manipulation. I can write it down in a script block.
</think>

<script>
case/eqpP => [[c1 c2]] /andP [c1n0 c2n0 e].
</script>

<think>
Now I have the equation `e : c1 *: p = c2 *: q` and I know both c1 and c2 are nonzero. I want to solve for p in terms of q.

From `c1 *: p = c2 *: q`, I should be able to get `p = (c1^-1 * c2) *: q` by multiplying both sides by c1^-1. Since c1 is nonzero, c1^-1 exists and this operation is valid.

But is there already a lemma that does this algebraic manipulation for me? Let me search...
</think>

<search>
A lemma scaling a polynomial equation to isolate one polynomial.
</search>

<think>
I don't see any existing lemma that directly performs this algebraic manipulation. The search results don't contain theorems that isolate one polynomial from a scaling equation like this.

So I need to prove this equality myself as an intermediate step. Since this is a key rewriting that I want to apply immediately to transform my goal, I'll use a `have` tactic with the rewrite arrow `->`.

The statement I want to prove and immediately apply is: `p = (c1^-1 * c2) *: q`. So my have tactic will look like `have -> : p = (c1^-1 * c2) *: q`. This should follow from the equation `c1 *: p = c2 *: q` by basic field arithmetic, but the proof involves showing that multiplication by c1^-1 is valid and applying associativity/commutativity properties.

To delegate this intermediate proof, I'll use a have block.
</think>

<have>
have -> : p = (c1^-1 * c2) *: q.
</have>

<think>
Excellent! Now my goal has been rewritten to `d %% ((c1^-1 * c2) *: q) %= d %% q`.

I can see that modpZr should apply here to give me `d %% ((c1^-1 * c2) *: q) = d %% q`, but modpZr requires that the scaling factor is nonzero. So I need to verify that `(c1^-1 * c2) != 0`.

Intuitively, this should be true because:
- c1 != 0 (from c1n0), so c1^-1 != 0
- c2 != 0 (from c2n0)
- The product of two nonzero elements should be nonzero

But I need to find the precise lemmas to establish this. Let me search for a lemma about when products are nonzero...
</think>

<search>
A lemma stating that a product is nonzero if its two factors are nonzero.
</search>

<think>
Mmh, no theorems among the results give me exactly what I want. But let me think, the mulf_eq0 lemma states that `(x * y == 0) = (x == 0) || (y == 0)` in integral domains. Taking the contrapositive: x * y != 0 if and only if x != 0 and y != 0. This is exactly what I want!

So to prove `(c1^-1 * c2) != 0`, I need to show `c1^-1 != 0` and `c2 != 0`.

I already have `c2 != 0` from c2n0. For c1^-1, I need to use the fact that c1 != 0 implies c1^-1 != 0. There should be a lemma about when inverses are zero...
</think>

<search>
A lemma about inverses being nonzero if the element is nonzero.
</search>

<think>
Ah! As previously, I must look the other way around: the invr_eq0 lemma states that `(x^-1 == 0) = (x == 0)`. Taking the contrapositive: x^-1 != 0 if and only if x != 0.

So I have:
- `c1^-1 != 0` follows from `c1 != 0` (which is c1n0) by invr_eq0
- `c2 != 0` is directly c2n0
- `(c1^-1 * c2) != 0` follows from both by mulf_eq0

But working with the boolean logic might be tricky. I'll need to use mulf_eq0 in the "backwards" direction, converting `~~ ((c1^-1 == 0) || (c2 == 0))` to `~~ (c1^-1 == 0) && ~~ (c2 == 0)`.

There should be a lemma about distributing negation over disjunction...
</think>

<search>
A lemma about distributing negation over disjunction.
</search>

<think>
Excellent! negb_or gives me `~~ (a || b) = ~~ a && ~~ b`, which is exactly what I need to distribute the negation.

Now, once I apply modpZr and verify the nonzero condition, I'll have `d %% ((c1^-1 * c2) *: q) = d %% q`. But my goal is to prove `d %% ((c1^-1 * c2) *: q) %= d %% q` - that these remainders are associates, not necessarily equal.

However, if two polynomials are equal, they're certainly associates! I need reflexivity of the associate relation...
</think>

<search>
A lemma proving the reflexivity of the associate relation.
</search>

<think>
Perfect! eqpxx provides reflexivity for the polynomial associate relation. So equal polynomials are associates.

Now I can construct my final tactic. I need to:

1. Apply modpZr to rewrite `d %% ((c1^-1 * c2) *: q)` to `d %% q`
2. This creates a side condition `(c1^-1 * c2) != 0` that I need to prove
3. Prove the nonzero condition using mulf_eq0, negb_or, invr_eq0, and my hypotheses
4. Apply eqpxx to show `d %% q %= d %% q` (reflexivity)

I should start by rewriting modpZr in the goal with `rewrite modpZr`. After applying this tactic, I'll have two goals:
- `(c1^-1 * c2) != 0` (the side condition from modpZr)
- `d %% q %= d %% q` (the transformed main goal)

The second goal is trivial - it's just reflexivity of the associate relation. I can apply eqpxx to solve it immediately. But I want to be efficient and handle both goals in the same tactic.

However, I need to be careful about the order and applicability. If I write `rewrite modpZr eqpxx`, then Coq will try to apply eqpxx to BOTH goals. But eqpxx is about polynomial associateness, while the first goal `(c1^-1 * c2) != 0` is about scalar nonzero-ness. The eqpxx rewriting will fail on the first goal. In SSReflect, I can use the ? operator to make a rewrite "optional" - it will apply where it can and skip where it can't. So rewrite modpZr ?eqpxx will successfully apply eqpxx only to the second goal.

Because I rewrite with eqpxx and do not apply it with a `apply` tactic, the second goal becomes the trivial `true` goal. Adding `//` to the tactic will automatically solve this goal. After `rewrite modpZr ?eqpxx //`, only the first goal remains.

Now I need to prove `(c1^-1 * c2) != 0`. I already worked out the logical chain for this:
1. By mulf_eq0: `(c1^-1 * c2 == 0) = (c1^-1 == 0) || (c2 == 0)`
2. So `(c1^-1 * c2) != 0` is equivalent to `~~ ((c1^-1 == 0) || (c2 == 0))`
3. By negb_or: `~~ ((c1^-1 == 0) || (c2 == 0)) = ~~ (c1^-1 == 0) && ~~ (c2 == 0)`
4. By invr_eq0: `~~ (c1^-1 == 0) && ~~ (c2 == 0) = ~~ (c1 == 0) && ~~ (c2 == 0)`, which is `(c1 != 0) && (c2 != 0)`

I can achieve this transformation by rewriting with mulf_eq0, negb_or, and invr_eq0 in sequence:
`rewrite modpZr ?eqpxx // mulf_eq0 negb_or invr_eq0`. After these rewrites, my goal becomes (c1 != 0) && (c2 != 0).

Now I can use my hypotheses. I have `c1n0 : c1 != 0`. If I rewrite with c1n0, it will transform `c1 != 0` to `true` in the goal. So `(c1 != 0) && (c2 != 0)` becomes `true && (c2 != 0)`.

In boolean algebra, `true && b` simplifies to just `b`. So after rewriting with c1n0, my goal becomes simply `c2 != 0` which is provable directly by an automatic tactic since I have `c2n0 : c2 != 0` in my hypothesis.

Solving this goal should terminate the proof so I can prefix my final tactic with `by` to autamitcally solve `c2 != 0` and finish the proof.

Finally, my tactic is `by rewrite modpZr ?eqpxx // mulf_eq0 negb_or invr_eq0 c1n0` and I can write it in a script block.
</think>

<script>
by rewrite modpZr ?eqpxx // mulf_eq0 negb_or invr_eq0 c1n0.
</script>

<think>
Excellent! The proof is complete.
</think>

## Final Instructions

**Maintain context awareness** - Track your goal, hypotheses, and current position throughout the proof.

**Simulate authentic discovery** - Write as if building the proof, never referencing given solutions or future steps and including genuine moments of research and discovery. You can even simulate failed search if it makes the simulation more real.

**Use the tools properly** - It is crucial that the tools are well used in the CoT examples you will write. Follow the instructions as much as possible and apply the tools at the right time. Precisely simulate their integration into the reasoning and how they help to finish the proof. Additionally, here are key points you must focus on:
- **Exhaustive searches** - Each dependency appearing in the code should have its dedicated search block
- **Precise searches** - Query clearly for a specific theorem without verbosity
- **Integrated reasoning** - Show how tool results inform your proof decisions
- **Maximize code detail** - Adapt the detail of each chain content to provide extremely detailed explanations justifying the need for each part of a chain. Break down every symbol, modifier, and operator.

**Follow the proof description logic** - Use the natural language proof description as your primary guide for the overall reasoning flow. You may improve or refine this logic if you see opportunities, but it provides the fundamental structure your CoT should follow. The natural language proof description do NOT follow the linear sequence of chains of the Coq proof and it should be the same for your CoT reasoning flow. For example, a chain can be written to set the stage for a subsequent chain. To maintain a faithful and logical simulation, you should start the reasoning about the subsequent chain, then realize you cannot write it down because certain prerequisites are missing. At this point, you should simulate the reasoning of the first chain, if no prerequisites are missing for the subsequent chain, you can continue its reasoning.

**Main rule: CoT coherence** - Never reference to knowledge that the reasoning LLM is not aware of. The proof description should NEVER be mentioned, a dependency should NEVER appear before its dedicated search block, a Coq code dedicated to a script or a have block should NEVER be written before the reasonings leading to each of its components. It is crucial that the CoT you generate gives the impression that the proof is being constructed through progressive reasoning and was not known in advance. The simulation should authentically represent discovery, not recall of a known solution.

Are you ready?

Here is the first math-comp theorem for which you need to simulate the CoT:
{input}
"""
