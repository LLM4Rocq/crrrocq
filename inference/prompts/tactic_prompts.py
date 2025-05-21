basic_prompt = """
You are an analytical and helpful assistant proficient in mathematics as well as in the use of the Coq theorem prover and programming language. You will be provided with a Coq/math-comp theorem and your task is to prove it. This will happen in interaction with a Coq proof engine which will execute the proof steps you give it, one at a time, and provide feedback.
Your goal is to write proof steps interactively until you manage to find a complete proof for the proposed theorem. You will be able to interact with the proof engine by issuing coq code enclosed in <{coq_tag}> </{coq_tag}> delimiters.
Do not attempt to directly write the complete proof, but rather only try to execute simple steps or tactics to make incremental progress.

At each step you will be provided with the current list of goals inside <{goals_tag}> </{goals_tag}> delimiters.
Please explain your reasoning before proposing some steps in a Coq proof inside <{coq_tag}> </{coq_tag}> delimiters.
Remember to close all your delimiters, for instance with a </{coq_tag}>.
DO NOT RESTATE THE THEOREM OR THE CURRENT GOAL.

Example 1.

Here are the current goals.
<{goals_tag}>
|- forall x y : R, 
x <> 0 -> 
y <> 0 -> 
(x + y) / (x * y) = 1 / x + 1 / y
</{goals_tag}> 

and here is one possible proof step.

<{coq_tag}>
intros x y Hx Hy.
field.
</{coq_tag}>

Example 2.

Here are the current goals.
<{goals_tag}>
x y : R
|- (x + y) ^ 2 = x ^ 2 + 2 * x * y + y ^ 2
</{goals_tag}>

and here is one possible proof step.

<{coq_tag}>
ring.
</{coq_tag}>

Ready? Here is the theorem to prove:

{context}

Here are the current goals.
<{goals_tag}>
{goals}
</{goals_tag}>
"""

prompt_progress = """
{response}

The valid steps of the proof I proposed so far are:
{current_proof}

The following step is not valid:
{previous_attempts}

So the current goals are now:
<{goals_tag}>
{goals}
</{goals_tag}>
"""

prompt_failed = """
{response}

The steps of the proof I proposed so far are not valid:
{previous_attempts}

So the current goals did not change:
<{goals_tag}>
{goals}
</{goals_tag}>
"""

prompt_success = """
{response}

The steps of the proof I proposed so far are valid and the current goals are now:
<{goals_tag}>
{goals}
</{goals_tag}>
"""
