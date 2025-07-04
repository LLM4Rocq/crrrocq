from .have import HaveTool
from .script import ScriptTool
from .search import SearchTool
from .base import BaseTool

DICT_TOOL = {
    "have": HaveTool,
    "script": ScriptTool,
    "search": SearchTool
}

def get_tool(tool_name: str, *args, **kwargs) -> BaseTool:
    if tool_name not in DICT_TOOL:
        raise ValueError(f"Unknown tool: {tool_name}")
    return DICT_TOOL[tool_name](*args, **kwargs)