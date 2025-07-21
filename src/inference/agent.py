from typing import List, Dict, Any, Optional, Union, Tuple
import re
import json
from dataclasses import dataclass

from .tools import Tool
from .llm import LLM


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
        self.RESULT_TAG = "result"

    def process_with_tools(
        self,
        llm: LLM,
        prompt: str,
        num_attempt: int = 1,
        max_iterations: int = 100,
    ) -> Status:
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

        # Create a list of stop sequences from tool tags
        stop_sequences = [f"</{tool.tag}>" for tool in self.tools.values()]

        n_iterations = 0
        active_prompt = [prompt]
        counter = num_attempt

        while n_iterations < max_iterations:
            responses = llm.generate_batch(active_prompt, stop_sequences)
            n_iterations += 1

            response = responses[0]  # Assuming we only have one active prompt

            new_prompt = prompt + response

            # Check if there's a tool call in the new response only
            tool_call = self.parser.extract_next_tool_call(response)

            if not tool_call:
                break

            tool_name, tool_input, start_pos, end_pos = tool_call

            current_tool = self.tools[tool_name]

            # Execute the tool
            tool_result = current_tool.run(tool_input)

            # Format the tool result
            if tool_name == "search":
                new_prompt += f"<{self.RESULT_TAG}>\n{tool_result['content']}\n</{self.RESULT_TAG}>"
                active_prompt = [new_prompt]
            elif tool_name == "coq-prover" or tool_name == "have-prover":
                if tool_result["status"] == "success":
                    if tool_result["is_complete"]:
                        # Proof is complete, return success immediately
                        return Status(success=True, proof=current_tool.env.proof)
                    else:
                        # Proof is progressing
                        result_text = f"The goal to prove is:\n{tool_result['goal']}"
                        new_prompt += (
                            f"<{self.RESULT_TAG}>\n{result_text}\n</{self.RESULT_TAG}>"
                        )
                        active_prompt = [new_prompt]
                else:
                    # Proof failed,
                    counter -= 1
                    if counter <= 0:
                        break
                    else:
                        new_prompt += f"<result>\nscript error\n</result>"
                        active_prompt = [new_prompt]

        llm.finalize_session(num_attempt, max_iterations, stop_sequences)
        return Status(success=False, proof=[])


# ===============================================
# Main Agent Class
# ===============================================


class MathProofAgent:
    """Main agent for formal mathematics proving."""

    def __init__(self, llm: LLM, search_tool: Tool, script_tool: Tool, have_tool: Tool):
        self.llm = llm
        self.tools = {
            search_tool.name: search_tool,
            script_tool.name: script_tool,
            have_tool.name: have_tool,
        }
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
            [f"{tool.instruction}" for tool in self.tools.values()]
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
4. **Reconsider**: Revise your overall proof strategy if necessaryAre you ready? Here is the initial goal.

<initial_goal>
{self.current_proof}
</initial goal>
"""
        return prompt

    def run_proof(
        self,
        num_attempt: int = 1,
        max_iterations: int = 100,
        verbose: bool = False,
    ) -> Status:
        """
        Run the proof using beam search.

        Args:
            beam_size: Number of parallel paths to explore (default: 1)
            verbose: Whether to print verbose output (default: False)
            session_name: Optional session name for LLM logging

        Returns:
            Status object with success flag and proof steps
        """
        # Build prompt
        prompt = self.build_prompt()

        # Generate response with tool support using beam search
        response = self.tool_handler.process_with_tools(
            llm=self.llm,
            prompt=prompt,
            num_attempt=num_attempt,
            max_iterations=max_iterations,
        )

        return response
