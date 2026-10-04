from typing import Any

from jsonschema import Draft202012Validator
from mcp.types import Tool

from app.config import validate_public_url
from app.mcp.tool_adapter import to_ollama_tool

ALLOWED_TOOLS = frozenset(
    {
        "browser_navigate",
        "browser_navigate_back",
        "browser_snapshot",
        "browser_find",
        "browser_click",
        "browser_hover",
    }
)


class ToolRegistry:
    def __init__(self, tools: list[Tool]):
        self.discovered = {tool.name: tool for tool in tools}
        self.enabled = {
            name: tool for name, tool in self.discovered.items() if name in ALLOWED_TOOLS
        }

    def ollama_tools(self) -> list[dict[str, Any]]:
        return [to_ollama_tool(tool) for tool in self.enabled.values()]

    def validate(self, name: str, arguments: Any) -> dict[str, Any]:
        if name not in self.discovered:
            raise ValueError(f"Unknown MCP tool: {name}")
        if name not in self.enabled:
            raise ValueError(f"MCP tool is discovered but disabled: {name}")
        if not isinstance(arguments, dict):
            raise ValueError("Tool arguments must be a JSON object.")
        schema = self.enabled[name].input_schema
        error = next(Draft202012Validator(schema).iter_errors(arguments), None)
        if error:
            raise ValueError(f"Invalid tool arguments: {error.message}")
        # The original schema is preserved for teaching. Client policy can be stricter.
        if set(arguments) - set(schema.get("properties", {})):
            raise ValueError("Unexpected tool argument.")
        if "filename" in arguments:
            raise ValueError("Saving browser output to files is disabled; omit filename.")
        if name == "browser_navigate":
            validate_public_url(arguments["url"])
        return arguments
