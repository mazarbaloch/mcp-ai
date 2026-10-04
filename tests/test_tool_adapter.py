from mcp.types import Tool

from app.mcp.tool_adapter import to_ollama_tool


def test_discovered_schema_preserved():
    schema = {
        "type": "object",
        "properties": {"target": {"type": "string"}},
        "required": ["target"],
        "additionalProperties": False,
    }
    tool = Tool(name="browser_click", description="Click an observed element", input_schema=schema)
    actual = to_ollama_tool(tool)
    assert actual == {
        "type": "function",
        "function": {
            "name": "browser_click",
            "description": "Click an observed element",
            "parameters": schema,
        },
    }
    actual["function"]["parameters"]["properties"].clear()
    assert tool.input_schema["properties"]  # No accidental mutation of discovery data.
