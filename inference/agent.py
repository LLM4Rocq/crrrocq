from typing import List, Dict, Any, Optional, Union, Tuple
import re

# ===============================================
# Custom Exception for Nested Tags
# ===============================================


class NestedTagError(Exception):
    """Exception raised when nested tags are detected."""

    pass


# ===============================================
# Parser Class
# ===============================================


class Parser:
    """Parse LLM outputs to identify tool calls."""

    def __init__(self):
        # Patterns for tool extraction - using non-greedy matching
        self.search_pattern = re.compile(r"<SEARCH>(.*?)</SEARCH>", re.DOTALL)
        self.coq_pattern = re.compile(r"<SCRIPT>(.*?)</SCRIPT>", re.DOTALL)

        # Patterns to detect nested tags
        self.nested_search_pattern = re.compile(
            r"<SEARCH>.*?<(SEARCH|SCRIPT)>", re.DOTALL
        )
        self.nested_coq_pattern = re.compile(r"<SCRIPT>.*?<(SEARCH|SCRIPT)>", re.DOTALL)

    def extract_next_tool_call(self, text: str) -> Optional[Tuple[str, str, int, int]]:
        """
        Extract the next tool call from text.

        Raises:
            NestedTagError: If nested tags are detected.

        Returns:
            Tuple of (tool_name, tool_input, start_position, end_position) or None if no tool call is found
        """
        # Check for nested tags first
        if self.nested_search_pattern.search(text) or self.nested_coq_pattern.search(
            text
        ):
            raise NestedTagError("Nested tool tags detected. Tags cannot be nested.")

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

        # Return the last match if any
        if all_matches:
            start_pos, end_pos, tool_name, tool_input = all_matches[-1]
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

        while True:
            # Generate text until a potential tool call
            response = llm.generate(current_prompt, ["</SEARCH>", "</SCRIPT>"])
            full_response += response

            # Check if there's a tool call
            tool_call = self.parser.extract_next_tool_call(full_response)

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
                        result_text = f"New goal: {tool_result['goal']}"
                    else:
                        result_text = f"Error: {tool_result['message']}"
                else:
                    result_text = f"Tool result: {json.dumps(tool_result, indent=2)}"

                # Append tool result to the response
                if tool_name == "search":
                    tool_response = f"<SEARCH>{tool_input}</SEARCH>\n{result_text}\n"
                elif tool_name == "coq-prover":
                    tool_response = f"<SCRIPT>{tool_input}</SCRIPT>\n{result_text}\n"

                # Update full response with tool response
                full_response = full_response[:end_pos] + tool_response

                # Continue generation with updated context
                current_prompt = prompt + full_response
            else:
                # Unknown tool, just continue
                break

        return full_response
