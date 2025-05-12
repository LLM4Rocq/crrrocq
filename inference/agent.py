from typing import List, Dict, Any, Optional, Union, Tuple
import re
import json
from dataclasses import dataclass

from tools import Tool
from llm import LLM


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

    def process_with_tools(self, llm: LLM, prompt: str, passk: int = 2) -> str:
        """
        Process LLM generation with tool support.

        This method handles the sequential interaction between the LLM and tools.
        It generates text until a tool call is detected, executes the tool,
        and then continues generation with the tool's response.
        """
        # full_responses = [prompt] * passk
        current_prompts = [prompt] * passk
        stops = [False] * passk

        if "coq-prover" in self.tools:
            coq_tools = [self.tools["coq-prover"].deepcopy() for _ in range(passk)]

        # Create a list of stop sequences from tool tags
        stop_sequences = [f"</{tool.tag}>" for tool in self.tools.values()]

        while not all(stops):
            # Generate text until a potential tool call
            responses = llm.generate_batch(current_prompts, stop_sequences)
            new_prompts = [f + r for (f, r) in zip(current_prompts, responses)]

            for i, response in enumerate(responses):
                # Check if there's a tool call
                tool_call = self.parser.extract_next_tool_call(response)

                if not tool_call:
                    # No tool call found, we're done
                    stops[i] = True

                tool_name, tool_input, start_pos, end_pos = tool_call

                if tool_name in self.tools:
                    if tool_name == "coq-prover":
                        current_tool = coq_tools[i]
                    else:
                        current_tool = self.tools[tool_name]

                    # Execute the tool
                    tool_result = current_tool.run(tool_input)

                    # Format the tool result
                    if tool_name == "search":
                        result_text = (
                            f"Search results: {json.dumps(tool_result, indent=2)}"
                        )
                    elif tool_name == "coq-prover":
                        if tool_result["status"] == "success":
                            if tool_result["is_complete"]:
                                result_text = "No more goals."
                                stop[i] = True
                            else:
                                result_text = f"Goals: {tool_result['goal']}"
                        else:
                            result_text = f"Error: {tool_result['message']}"
                            stop[i] = True
                    else:
                        result_text = (
                            f"Tool result: {json.dumps(tool_result, indent=2)}"
                        )

                    tool_response = (
                        f"<{self.RESULT_TAG}>\n{result_text}\n</{self.RESULT_TAG}>"
                    )

                    # Update prompts with tool response
                    new_prompts[i] = new_prompts[i] + tool_response
                else:
                    stops[i] = True

                current_prompts = [
                    p for (p, i) in enumerate(new_prompts) if not stops[i]
                ]

        return full_response


# ===============================================
# Main Agent Class
# ===============================================


@dataclass
class Status:
    success: bool
    proof: List[str]


class MathProofAgent:
    """Main agent for formal mathematics proving."""

    def __init__(self, llm: LLM, search_tool: Tool, coq_tool: Tool):
        self.llm = llm
        self.tools = {search_tool.name: search_tool, coq_tool.name: coq_tool}
        self.tool_handler = ToolHandler(parser=Parser(), tools=self.tools)
        self.current_proof = coq_tool.env.thm_code
        self.coq_tool = coq_tool
        self.search_tool = search_tool

    def build_prompt(self) -> str:
        """Build the prompt for the LLM."""

        # Get available tools with their descriptions
        tool_descriptions = "\n".join(
            [
                f"{i+1}. {tool.name}: {tool.description}"
                for i, tool in enumerate(self.tools.values())
            ]
        )

        # Build instructions for tool usage with proper tags
        tool_instructions = "\n".join(
            [
                f"- To use the {tool.name} tool, use: <{tool.tag}>your input</{tool.tag}>"
                for tool in self.tools.values()
            ]
        )

        # Build the prompt
        prompt = f"""You are a formal mathematics proving assistant.

Available tools:
{tool_descriptions}

How to use tools:
{tool_instructions}

Here is the theorem I am trying to prove:
{self.current_proof}
Please help me progress with this proof. Explain your reasoning step by step.
"""

        prompt = """
You are an analytical and helpful assistant proficient in mathematics as well as in the use of the Coq theorem prover and programming language. You will be provided with a Coq/math-comp theorem and your task is to prove it. This will happen in interaction with a Coq proof engine which will execute the proof steps you give it, one at a time, and provide feedback.
Your goal is to write proof steps interactively until you manage to find a complete proof for the proposed theorem. You will be able to interact with the proof engine by issuing coq code enclosed in <SCRIPT> </SCRIPT> delimiters.
Do not attempt to directly write the complete proof, but rather only try to execute simple steps or tactics to make incremental progress.

At each step you will be provided with the current list of goals inside <GOALS> </GOALS> delimiters.
Please explain your reasoning before proposing a Coq proof inside <SCRIPT> </SCRIPT> delimiters.
Remember to close all your delimters, for instance with a </SCRIPT>.
DO NOT RESTATE THE THEOREM OR THE CURRENT GOAL.

Example 1.

Here are the current goals.
<GOALS>
n, m, p : nat
|- nat, n + (m + p) = m + (n + p)
</GOALS> 

and here is one possible proof step.

<SCRIPT>
rewrite Nat.add_assoc.
</Script>

Example 2.
Here are the current goals.

<GOALS>
f nat -> nat 
I forall n : nat, n = f (f n) 
n1n2 nat 
H f n1 = f n2 
|- n1 = n2
</GOALS>

and here is one possible proof step.

<SCRIPT>
rewrite (I n1).
<SCRIPT>


Ready?

Here are the current goals.
<GOALS>
{self.current_proof}
</GOALS>
        """

        return prompt

    def run_proof(self, verbose: bool = False) -> Status:
        # Build prompt
        prompt = self.build_prompt()

        # Generate response with tool support
        response = self.tool_handler.process_with_tools(self.llm, prompt)

        if verbose:
            print("LLM final response:", response)

        if self.coq_tool.env.proof_finished:
            return Status(success=True, proof=self.coq_tool.env.proof)
        else:
            return Status(success=False, proof=self.coq_tool.env.proof)
