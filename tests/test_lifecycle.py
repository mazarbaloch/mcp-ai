import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.config import Settings
from app.errors import error_message
from app.mcp import playwright_client


@pytest.mark.parametrize("failure", [False, True])
async def test_sdk_session_exits_and_temp_workspace_removed(monkeypatch, registry, failure):
    lifecycle = []
    params_used = []

    @asynccontextmanager
    async def client(params, **kwargs):
        params_used.append(params)
        lifecycle.append("enter")
        try:
            yield AsyncMock(
                list_tools=AsyncMock(
                    return_value=SimpleNamespace(
                        tools=list(registry.discovered.values()),
                        next_cursor=None,
                    )
                )
            )
        finally:
            lifecycle.append("exit")

    monkeypatch.setattr(playwright_client, "Client", client)
    monkeypatch.setattr(playwright_client.shutil, "which", lambda name: name)

    async def use():
        async with playwright_client.connect_playwright(Settings()) as (_, discovered):
            assert "browser_navigate" in discovered.enabled
            if failure:
                raise RuntimeError("test failure")

    if failure:
        with pytest.raises(RuntimeError, match="test failure"):
            await use()
    else:
        await use()
    from pathlib import Path

    assert lifecycle == ["enter", "exit"]
    assert not await asyncio.to_thread(Path(params_used[0].cwd).exists)
    assert "--headless" not in params_used[0].args
    assert "--no-webmcp" in params_used[0].args


async def test_missing_node_is_actionable(monkeypatch):
    monkeypatch.setattr(playwright_client.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="Install Node.js"):
        async with playwright_client.connect_playwright(Settings()):
            pytest.fail("Should not connect")


def test_browser_is_isolated_and_downloads_disabled():
    config = playwright_client.server_config(Settings())
    assert config["browser"]["launchOptions"]["headless"] is False
    assert config["browser"]["contextOptions"]["acceptDownloads"] is False
    assert config["browser"]["isolated"] is True


def test_nested_errors_show_actual_cause():
    assert (
        error_message(
            ExceptionGroup(
                "tasks",
                [
                    ExceptionGroup(
                        "inner",
                        [
                            RuntimeError("Browser executable missing"),
                        ],
                    )
                ],
            )
        )
        == "Browser executable missing"
    )
    assert "timed out" in error_message(TimeoutError())
