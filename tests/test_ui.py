import asyncio
from contextlib import asynccontextmanager

import pytest
from conftest import FakeModel, call, final, requesting

from app import main


def fake_connections(monkeypatch, registry, mcp, model):
    lifecycle = []

    @asynccontextmanager
    async def ollama(settings):
        yield model, "Available locally"

    @asynccontextmanager
    async def playwright(settings):
        owner = asyncio.current_task()
        lifecycle.append("enter")
        try:
            yield mcp, registry
        finally:
            assert asyncio.current_task() is owner
            lifecycle.append("exit")

    monkeypatch.setattr(main, "connect_ollama", ollama)
    monkeypatch.setattr(main, "connect_playwright", playwright)
    return lifecycle


async def test_ui_streams_activity_then_closes(monkeypatch, registry, mcp):
    lifecycle = fake_connections(monkeypatch, registry, mcp, FakeModel(requesting(call()), final()))
    updates = [item async for item in main.research("https://example.org/", "Read page", "test")]
    assert updates[-1][0] == "Observed answer: https://example.org/"
    assert "Closed" in updates[-1][1]
    assert updates[-1][2][0]["source"] == "Playwright MCP"
    assert updates[-1][3]["discovered_count"] == 4
    assert lifecycle == ["enter", "exit"]


async def test_ui_cancellation_exits_in_owner_task(monkeypatch, registry, mcp):
    waiting = asyncio.Event()

    class SlowModel:
        async def chat(self, messages, tools):
            waiting.set()
            await asyncio.Event().wait()

    lifecycle = fake_connections(monkeypatch, registry, mcp, SlowModel())
    stream = main.research("https://example.org/", "Read page", "test")
    await anext(stream)
    await asyncio.wait_for(waiting.wait(), timeout=2)
    await stream.aclose()
    assert lifecycle == ["enter", "exit"]


async def test_ui_invalid_url_is_useful(monkeypatch):
    def never_connect(*args):
        pytest.fail("Invalid URL should be rejected before connecting")

    monkeypatch.setattr(main, "connect_ollama", never_connect)
    updates = [item async for item in main.research("file:///private", "Read page", "test")]
    assert "public http:// or https://" in updates[-1][0]


async def test_ui_timeout_closes_browser_and_explains(monkeypatch, registry, mcp):
    class TimeoutModel:
        async def chat(self, messages, tools):
            raise TimeoutError

    lifecycle = fake_connections(monkeypatch, registry, mcp, TimeoutModel())
    updates = [item async for item in main.research("https://example.org/", "Read page", "test")]
    assert "timed out" in updates[-1][0]
    assert lifecycle == ["enter", "exit"]
