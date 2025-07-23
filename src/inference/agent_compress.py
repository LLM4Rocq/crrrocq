from typing import List, Dict, Any, Optional, Union, Tuple
from dataclasses import dataclass
from collections import defaultdict
import re
import json
from copy import deepcopy

from ..tools.base import ToolError
from ..tools.factory import get_tool
from ..llm.factory import get_llm

from .agent import MathAgent

class MathAgentCompress(MathAgent):
    """Compress agent for formal mathematics proving."""
    def build_blocks(self) -> str:
        """Agregate blocks into string with compression method."""
        subblocks = []
        reach_kind = {k:False for k in self.tools.keys()}
        last_result = None
        for block in self.blocks[::-1]:
            kind = block['kind']
            if kind == 'result':
                last_result = block
                continue
            elif kind in reach_kind:
                if not reach_kind[kind]:
                    subblocks = [block, last_result] + subblocks
                    reach_kind[kind] = True
                else:
                    subblocks = [block] + subblocks
            else:
                subblocks = [block] + subblocks
        output = "\n".join(
            [
            f"<{block['kind']}>\n{block['content']}\n</{block['kind']}>"
            for block in subblocks
            ]
        )
        if not self.blocks:
            return "<think>\n"
        return output