from dataclasses import asdict

import pytest
from conftest import FakeModel, call, final, requesting
from mcp.types import CallToolResult, TextContent

from app.agent import run_agent
from app.config import Settings
from app.models import ResearchState


async def run(model, mcp, registry, **settings):
    updates = []

    async def update(state):
        updates.append(asdict(state))

    state = await run_agent(
        "Find the heading",
        "https://example.org/",
        model,
        mcp,
        registry,
        Settings(**settings),
        ResearchState(),
        update,
    )
    return state, updates


async def test_one_call_then_answer_and_activity(mcp, registry):
    model = FakeModel(requesting(call()), final())
    state, updates = await run(model, mcp, registry)
    assert state.completed
    assert state.visited == ["https://example.org/"]  # The link wasn't visited.
    event = state.activity[0]
    assert event.sequence == 1
    assert event.tool == "browser_navigate"
    assert event.arguments == {"url": "https://example.org/"}
    assert event.source == "Playwright MCP"
    assert event.status == "success"
    assert event.duration_ms >= 0
    assert "Observed heading" in event.result_preview
    assert any(update["activity"] for update in updates)
    assert model.history[1][-1]["role"] == "tool"
    assert model.history[1][-1]["tool_name"] == "browser_navigate"


async def test_sequential_calls(mcp, registry):
    model = FakeModel(
        requesting(call()),
        requesting(call("browser_find", {"text": "heading"})),
        requesting(call("browser_snapshot", {})),
        final(),
    )
    state, _ = await run(model, mcp, registry)
    assert state.completed
    assert mcp.call_tool.await_count == 3


async def test_multiple_calls_preserve_order(mcp, registry):
    model = FakeModel(requesting(call(), call("browser_snapshot", {})), final())
    state, _ = await run(model, mcp, registry)
    assert [e.tool for e in state.activity] == ["browser_navigate", "browser_snapshot"]
    assert [m["role"] for m in model.history[-1]] == [
        "system",
        "user",
        "assistant",
        "tool",
        "tool",
    ]


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("unknown", {}),
        ("browser_evaluate", {}),
        ("browser_navigate", {"url": 42}),
        ("browser_navigate", "{bad json"),
        ("browser_navigate", []),
        ("browser_snapshot", {"filename": "private.txt"}),
        ("browser_navigate", {"url": "file:///private"}),
    ],
)
async def test_blocked_call_never_reaches_mcp(mcp, registry, name, arguments):
    model = FakeModel(requesting(call(name, arguments)), final())
    state, _ = await run(model, mcp, registry)
    mcp.call_tool.assert_not_awaited()
    assert state.activity[0].status == "blocked"
    assert not state.completed


async def test_tool_error_can_be_corrected(mcp, registry, page_result):
    mcp.call_tool.side_effect = [
        CallToolResult(
            is_error=True, content=[TextContent(type="text", text="Navigation failed: timeout")]
        ),
        page_result,
    ]
    model = FakeModel(requesting(call()), requesting(call()), final())
    state, _ = await run(model, mcp, registry)
    assert [e.status for e in state.activity] == ["error", "success"]
    assert state.completed
    assert "Navigation failed" in model.history[1][-1]["content"]


async def test_disconnect_stops_gracefully(mcp, registry):
    mcp.call_tool.side_effect = ConnectionError("Server disconnected")
    state, _ = await run(FakeModel(requesting(call())), mcp, registry)
    assert not state.completed
    assert "disconnected" in state.answer
    assert state.activity[0].status == "error"


async def test_no_calls_does_not_present_ungrounded_answer(mcp, registry):
    state, _ = await run(FakeModel(final("Invented fact")), mcp, registry)
    assert "Invented fact" not in state.answer
    assert not state.completed


async def test_hard_budget_counts_each_call_in_a_batch(mcp, registry):
    model = FakeModel(
        requesting(call(), call("browser_snapshot", {}), call("browser_snapshot", {}))
    )
    state, _ = await run(model, mcp, registry, max_tool_steps=2)
    assert mcp.call_tool.await_count == 2
    assert "within 2 tool calls" in state.answer
    assert not state.completed


async def test_final_answer_allowed_at_limit(mcp, registry):
    state, _ = await run(FakeModel(requesting(call()), final()), mcp, registry, max_tool_steps=1)
    assert state.completed


async def test_thinking_removed_from_conversation(mcp, registry):
    response = requesting(call()) | {"thinking": "private reasoning"}
    model = FakeModel(response, final())
    state, _ = await run(model, mcp, registry)
    assert "private reasoning" not in str(model.history)
    assert "private reasoning" not in str(asdict(state))


async def test_metadata_only_requires_content_before_answer(mcp, registry, page_result):
    mcp.call_tool.side_effect = [
        CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=(
                        "### Page\n- Page URL: https://example.org/\n"
                        "### Snapshot\n- [Snapshot](./page.yml)"
                    ),
                )
            ]
        ),
        page_result,
    ]
    model = FakeModel(
        requesting(call()),
        final("Premature answer"),
        requesting(call("browser_snapshot", {})),
        final(),
    )
    state, _ = await run(model, mcp, registry)
    assert state.completed
    assert mcp.call_tool.await_count == 2
    assert "metadata" in model.history[2][-1]["content"]


async def test_wrong_starting_page_is_blocked(mcp, registry):
    state, _ = await run(
        FakeModel(
            requesting(
                call(
                    "browser_navigate",
                    {
                        "url": "https://other.org/",
                    },
                )
            ),
            final(),
        ),
        mcp,
        registry,
    )
    mcp.call_tool.assert_not_awaited()
    assert "First navigate" in state.activity[0].result_preview
