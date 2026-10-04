from copy import deepcopy
from typing import Any

from mcp.types import Tool


def to_ollama_tool(tool: Tool) -> dict[str, Any]:
    """Copy actual MCP 2.x definitions; do not invent browser function schemas."""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": deepcopy(tool.input_schema),
        },
    }
