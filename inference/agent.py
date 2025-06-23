from typing import List, Dict, Any, Optional, Union, Tuple
import re
import json
from dataclasses import dataclass

from tools import Tool
from llm import LLM


@dataclass
class Status:
    success: bool
    proof: List[str]


# ===============================================
# Parser Class
# ===============================================


class Parser:
    """Parse LLM outputs to identify tool calls."""

    def __init__(self):
        # We'll dynamically create patterns based on registered tools
        self.tool_patterns = {}

    def register_tool(self, tool_name: str, tag: str):
        """
        Register a tool with its XML tag for pattern matching.

        Args:
            tool_name: The name of the tool
            tag: The XML tag to use for this tool (without angle brackets)
        """
        # Create a regex pattern for this tag - using non-greedy matching
        pattern = re.compile(f"<{tag}>(.*?)</{tag}>", re.DOTALL)
        self.tool_patterns[tool_name] = pattern

    def extract_next_tool_call(self, text: str) -> Optional[Tuple[str, str, int, int]]:
        """
        Extract the next tool call from text.

        Returns:
            Tuple of (tool_name, tool_input, start_position, end_position) or None if no tool call is found
        """
        # Find all matches for each registered pattern
        all_matches = []

        for tool_name, pattern in self.tool_patterns.items():
            matches = [
                (m.start(), m.end(), tool_name, m.group(1).strip())
                for m in pattern.finditer(text)
            ]
            all_matches.extend(matches)

        # Sort by position to get the first occurrence
        all_matches.sort()

        # Return the first match if any
        if all_matches:
            start_pos, end_pos, tool_name, tool_input = all_matches[0]
            return (tool_name, tool_input, start_pos, end_pos)

        return None


# ===============================================
# Tool Handler Class
# ===============================================


class ToolHandler:
    """
    Handles the interaction between LLM output and tools.

    This class is responsible for:
    1. Detecting tool calls in LLM output
    2. Executing tools
    3. Updating the LLM context with tool results
    """

    def __init__(self, parser: Parser, tools: Dict[str, Tool]):
        self.parser = parser
        self.tools = tools

        # Register all tools with the parser
        for tool_name, tool in tools.items():
            self.parser.register_tool(tool_name, tool.tag)

        # Define a constant for the result tag
        self.RESULT_TAG = "RESULT"

    def process_with_tools(self, llm: LLM, prompt: str, beam_size: int = 1) -> Status:
        """
        Process LLM generation with tool support using beam search.

        This method handles the sequential interaction between the LLM and tools,
        exploring multiple possible paths (beam_size) and returning the first successful one.

        Args:
            llm: The language model to use
            prompt: The initial prompt
            beam_size: Number of parallel paths to explore (default: 1)

        Returns:
            Status object with success flag and proof steps
        """
        # Initialize fixed-size arrays for all beams
        all_prompts = [prompt] * beam_size

        # Create deep copies of the Coq prover tool for each beam
        if "coq-prover" in self.tools:
            all_coq_tools = [
                self.tools["coq-prover"].deepcopy() for _ in range(beam_size)
            ]
        else:
            all_coq_tools = [None] * beam_size

        # Track which beams are active
        active_indices = list(range(beam_size))

        # Create a list of stop sequences from tool tags
        stop_sequences = [f"</{tool.tag}>" for tool in self.tools.values()]

        # Continue as long as there are active beams
        while active_indices:
            # Collect only the active prompts for the LLM
            active_prompts = [all_prompts[i] for i in active_indices]

            # Generate responses only for active beams
            responses = llm.generate_batch(active_prompts, stop_sequences)

            # New set of active indices for the next iteration
            new_active_indices = []

            # Process each response for active beams
            for idx_pos, idx in enumerate(active_indices):
                response = responses[idx_pos]

                # Update the full prompt for this beam
                all_prompts[idx] += response

                # Check if there's a tool call in the new response only
                tool_call = self.parser.extract_next_tool_call(response)

                if not tool_call:
                    # No tool call found, this beam is done
                    continue

                tool_name, tool_input, start_pos, end_pos = tool_call

                # Use the corresponding tool instance for this beam
                if tool_name == "coq-prover":
                    current_tool = all_coq_tools[idx]
                else:
                    current_tool = self.tools[tool_name]

                # Execute the tool
                tool_result = current_tool.run(tool_input)

                # Format the tool result
                if tool_name == "search":
                    result_text = f"Search results: {json.dumps(tool_result, indent=2)}"
                    # Keep this beam active
                    all_prompts[
                        idx
                    ] += f"<{self.RESULT_TAG}>\n{result_text}\n</{self.RESULT_TAG}>"
                    new_active_indices.append(idx)
                elif tool_name == "coq-prover":
                    if tool_result["status"] == "success":
                        if tool_result["is_complete"]:
                            # Proof is complete, return success immediately
                            return Status(success=True, proof=current_tool.env.proof)
                        else:
                            # Proof is progressing, keep this beam active
                            result_text = f"Goals: {tool_result['goal']}"
                            all_prompts[
                                idx
                            ] += f"<{self.RESULT_TAG}>\n{result_text}\n</{self.RESULT_TAG}>"
                            new_active_indices.append(idx)
                    else:
                        # Proof failed, discard this beam (don't add to new_active_indices)
                        continue

            # Update active indices for next iteration
            active_indices = new_active_indices

        # If we've reached here, no beam succeeded
        return Status(success=False, proof=[])


# ===============================================
# Main Agent Class
# ===============================================


class MathProofAgent:
    """Main agent for formal mathematics proving."""

    def __init__(self, llm: LLM, search_tool: Tool, script_tool: Tool, have_tool: Tool):
        self.llm = llm
        self.tools = {search_tool.name: search_tool, script_tool.name: script_tool, have_tool.name: have_tool}
        self.tool_handler = ToolHandler(parser=Parser(), tools=self.tools)
        self.current_proof = script_tool.env.thm_code

    def build_prompt(self) -> str:
        """Build the prompt for the LLM."""

        # Get available tools with their descriptions
        tool_descriptions = "\n".join(
            [
                f"<{tool.tag}> {tool.description} </{tool.tag}>"
                for tool in self.tools.values()
            ]
        )

        # Build instructions for tool usage with proper tags
        tool_instructions = "\n".join(
            [
                f"{tool.instruction}"
                for tool in self.tools.values()
            ]
        )

        # Build the prompt
        prompt = f"""# Coq Proof Generation Assistant

## Your Role

You are an expert Coq proof assistant specializing in formal mathematics with mathcomp. Your primary objective is to construct complete, correct proofs for given theorems through systematic interaction with the Coq environment.

## Workflow Structure

You operate through a structured chain-of-thought process using specialized XML blocks:

```xml
<think>Strategic analysis and proof planning</think>
{tool_descriptions}
<result> Results from the tools </result>
```

## Tool Reference

### 🤔 Think Block
**Strategic reasoning and proof planning**
- Analyze current goals and mathematical context
- Develop proof strategies and identify key insights
- Plan tactical sequences and explain reasoning
- Consider alternative approaches when blocked

{tool_instructions}

## Error Handling Strategy

When tactics fail:
1. **Analyze**: Examine error messages for specific issues
2. **Search**: Look for alternative lemmas or approaches  
3. **Simplify**: Break complex tactics into smaller steps
4. **Reconsider**: Revise your overall proof strategy if necessary

## Example

**example input**:
<statement>
Lemma eqp_modpr d p q : p %= q -> (d %% p) %= (d %% q).
</statement>

<initial_goal>
F  : fieldType
d, p, q  : {{poly F}}
|-p %= q -> d %% p %= d %% q
</initial goal>

**example output**:
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


Are you ready? Here is the initial goal.

<initial_goal>
{self.current_proof}
</initial goal>
"""
        return prompt

    def run_proof(self, beam_size: int = 1, verbose: bool = False) -> Status:
        """
        Run the proof using beam search.

        Args:
            beam_size: Number of parallel paths to explore (default: 1)
            verbose: Whether to print verbose output (default: False)

        Returns:
            Status object with success flag and proof steps
        """
        # Build prompt
        prompt = self.build_prompt()

        # Generate response with tool support using beam search
        response = self.tool_handler.process_with_tools(self.llm, prompt, beam_size)

        return response
