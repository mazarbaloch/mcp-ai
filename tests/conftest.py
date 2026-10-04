from copy import deepcopy
from unittest.mock import AsyncMock

import pytest
from mcp.types import CallToolResult, TextContent, Tool

from app.mcp.tool_registry import ToolRegistry


@pytest.fixture
def registry():
    return ToolRegistry(
        [
            Tool(
                name="browser_navigate",
                description="Navigate",
                input_schema={
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"],
                    "additionalProperties": False,
                },
            ),
            Tool(
                name="browser_snapshot",
                description="Snapshot",
                input_schema={
                    "type": "object",
                    "properties": {"filename": {"type": "string"}},
                },
            ),
            Tool(
                name="browser_find",
                description="Find",
                input_schema={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                },
            ),
            Tool(
                name="browser_evaluate", description="Execute JS", input_schema={"type": "object"}
            ),
        ]
    )


@pytest.fixture
def page_result():
    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text=(
                    "### Page\n- Page URL: https://example.org/\n- Page Title: Example\n"
                    '### Snapshot\n- heading "Observed heading" [ref=e1]\n'
                    '- link "Details" [ref=e2]:\n  - /url: https://example.org/details\n'
                ),
            )
        ]
    )


@pytest.fixture
def mcp(page_result):
    return AsyncMock(call_tool=AsyncMock(return_value=page_result))


def call(name="browser_navigate", arguments=None):
    return {
        "function": {
            "name": name,
            "arguments": ({"url": "https://example.org/"} if arguments is None else arguments),
        }
    }


class FakeModel:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.history = []

    async def chat(self, messages, tools):
        self.history.append(deepcopy(messages))
        return next(self.responses)


def requesting(*calls):
    return {"role": "assistant", "content": "", "tool_calls": list(calls)}


def final(text="Observed answer: https://example.org/"):
    return {"role": "assistant", "content": text}
