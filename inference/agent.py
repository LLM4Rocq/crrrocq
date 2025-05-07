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
        # Patterns for tool extraction - using non-greedy matching
        self.search_pattern = re.compile(r"<SEARCH>(.*?)</SEARCH>", re.DOTALL)
        self.coq_pattern = re.compile(r"<SCRIPT>(.*?)</SCRIPT>", re.DOTALL)

    def extract_next_tool_call(self, text: str) -> Optional[Tuple[str, str, int, int]]:
        """
        Extract the next tool call from text.

        Returns:
            Tuple of (tool_name, tool_input, start_position, end_position) or None if no tool call is found
        """

        # Find all matches for each pattern
        search_matches = [
            (m.start(), m.end(), "search", m.group(1).strip())
            for m in self.search_pattern.finditer(text)
        ]

        coq_matches = [
            (m.start(), m.end(), "coq-prover", m.group(1).strip())
            for m in self.coq_pattern.finditer(text)
        ]

        # Combine and sort by position
        all_matches = sorted(search_matches + coq_matches)

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

    def process_with_tools(self, llm: LLM, prompt: str) -> str:
        """
        Process LLM generation with tool support.

        This method handles the sequential interaction between the LLM and tools.
        It generates text until a tool call is detected, executes the tool,
        and then continues generation with the tool's response.
        """
        full_response = ""
        current_prompt = prompt
        stop = False

        while True:
            # Generate text until a potential tool call
            response = llm.generate(current_prompt, ["</SEARCH>", "</SCRIPT>"])
            full_response += response

            # Check if there's a tool call
            tool_call = self.parser.extract_next_tool_call(response)

            if not tool_call:
                # No tool call found, we're done
                break

            tool_name, tool_input, start_pos, end_pos = tool_call

            if tool_name in self.tools:
                # Execute the tool
                tool_result = self.tools[tool_name].run(tool_input)

                # Format the tool result
                if tool_name == "search":
                    result_text = f"Search results: {json.dumps(tool_result, indent=2)}"
                elif tool_name == "coq-prover":
                    if tool_result["status"] == "success":
                        if tool_result["is_complete"]:
                            result_text = "No more goals."
                            stop = True
                        else:
                            result_text = f"Goals: {tool_result['goal']}"
                    else:
                        result_text = f"Error: {tool_result['message']}"
                        stop = True
                else:
                    result_text = f"Tool result: {json.dumps(tool_result, indent=2)}"

                tool_response = f"<RESULT>\n{result_text}\n</RESULT>"

                # Update full response with tool response
                full_response = full_response + tool_response
                if stop:
                    break

                # Continue generation with updated context
                current_prompt = prompt + full_response
            else:
                # Unknown tool, just continue
                break

        return full_response


# ===============================================
# Main Agent Class
# ===============================================


@dataclass
class Status:
    success: bool
    proof: str


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

        # Get available tools
        tool_descriptions = "\n".join(
            [
                f"{i+1}. {tool.name}: {tool.description}"
                for i, tool in enumerate(self.tools.values())
            ]
        )

        # Build the prompt
        prompt = f"""You are a formal mathematics proving assistant.

Available tools:
{tool_descriptions}

- To search for theorems or definitions, use: <SEARCH>your search query</SEARCH>
- To apply Coq tactics, use: <SCRIPT>your tactics</SCRIPT>

Here is the theorem I am trying to prove:
{self.current_proof}
Please help me progress with this proof. Explain your reasoning step by step.
"""
        return prompt

    def run_proof(self, verbose: bool = False) -> Status:
        # Build prompt
        prompt = self.build_prompt()

        # Generate response with tool support
        response = self.tool_handler.process_with_tools(self.llm, prompt)

        if verbose:
            print("LLM Response:", response)

        if self.coq_tool.env.proof_finished:
            return Status(success=True, proof=self.coq_tool.env.proof)
        else:
            return Status(success=False, proof=self.coq_tool.env.proof)
