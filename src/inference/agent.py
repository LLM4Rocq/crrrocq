from typing import List, Dict, Any, Optional, Union, Tuple
from dataclasses import dataclass
import re
from copy import deepcopy

from ..tools.factory import get_tool
from ..llm.factory import get_llm

class ParsingBlockError(Exception):
    def __init__(self, message):
        self.message = message

class MathAgentError(Exception):
    def __init__(self, message):
        self.message = message
    
def parse_output(output: str, max_len=2, kinds=['search', 'think', 'script', 'have']):
    """Parse LLM output into list of blocks {"kind":..., "content":...}"""
    pattern = re.compile(
        r"<(?P<kind>\w+)>\s*(?P<content>.*?)\s*<\/\1>",
        re.DOTALL | re.MULTILINE,
    )
    result = []
    for m in pattern.finditer(output):
        kind = m.group("kind").strip()
        if kind not in kinds:
            raise ParsingBlockError(message=f'Issue when parsing:\n"{output}"')
        block = {
            "kind": m.group("kind").strip(),
            "content": m.group("content").strip()
        }
        result.append(block)
    if max_len < len(result):
        raise ParsingBlockError(message=f'Issue when parsing:\n"{output}"')
    return result

class MathAgent:
    """Main agent for formal mathematics proving."""

    def __init__(self, config):
        self.config = config
        self.tools = {}
        self.logs = []
        self.blocks = []
        for tool_name, tool_config in config['tools'].items():
            self.tools[tool_name] = get_tool(tool_name)(**tool_config)
        self.instruct = self.build_instruct()
        self.llm = get_llm(config['llm_name'])(**config['llm_config'])

    def duplicate(self, reset_blocks=False) -> Any:
        """Duplicate current agent."""
        agent = MathAgent(self.config)
        self.transfer_tools(agent)
        if not reset_blocks:
            agent.blocks = deepcopy(self.blocks)
        return agent

    def transfer_tools(self, otheragent):
        """Transfer tool from current agent agent to other agent"""
        for tool_name in self.tools:
            otheragent.tools[tool_name].state = self.tools[tool_name].state

    def start_thm(self, thm_name):
        """Intialize agent to prove theorem."""
        assert "script" in self.tools, "Missing script tool."
        self.tools["script"].start_thm(thm_name)

    def build_instruct(self) -> str:
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
        prompt = self.config("prompt_template").format(tool_descriptions=tool_descriptions, tool_instructions=tool_instructions)
        return prompt

    def build_blocks(self) -> str:
        """Agregate blocks into string."""
        # TODO: for the moment, HF apply chat template require non empty assistant content for continuation
        if not self.blocks:
            return "<think>\n"
        
        output = "\n".join(
            [
                f"<{block['kind']}>\n{block['content']}\n</{block['kind']}>"
                for block in self.blocks
            ]
        )
        return output

    def run_proof(self, goals_init: List[str]=[]):
        """
        Run the proof.
        """
        assert "script" in self.tools, "Missing script tool."
        curr_depth = 0
        while curr_depth < self.config['max_depth']:
            messages = [
                {"role": "user", "content": self.instruct},
                {"role": "assistant", "content": self.build_blocks()}
            ]
            output = self.llm.generate(messages)
            new_blocks = parse_output(output)
            blocks += new_blocks
            last_block = new_blocks[-1]

            result = self.tools[last_block['kind']](last_block['content'], agent=self, **self.config['tools_param'])
            blocks.append({"kind": "result", "content": result})

            curr_depth += 1
            if goals_init:
                match_subgoals = [
                    goal_init['ty'] == goal_new['ty']
                    for goal_init, goal_new in zip(goals_init, self.tools['script'])
                ]
                if all(match_subgoals):
                    return
            if not self.tools['script'].goals:
                return
        raise MathAgentError("Reach max depth without generating a complete proof.")
