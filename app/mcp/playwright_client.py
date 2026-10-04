"""MCP SDK 2.1: a real stdio subprocess, with one task owning its lifecycle."""

import json
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from mcp import Client, StdioServerParameters

from app.config import Settings
from app.mcp.tool_registry import ToolRegistry


def server_config(settings: Settings) -> dict:
    return {
        "browser": {
            "browserName": "chromium",
            "isolated": True,
            "launchOptions": {"channel": "chromium", "headless": settings.playwright_headless},
            "contextOptions": {"acceptDownloads": False, "serviceWorkers": "block"},
        },
    }


@asynccontextmanager
async def connect_playwright(settings: Settings):
    command = shutil.which("npx")
    if not command or not shutil.which("node"):
        raise RuntimeError("Node.js/npm/npx missing. Install Node.js LTS and reopen PowerShell.")
    # Empty, temporary workspace: no personal browser profile or repository file access.
    with TemporaryDirectory(prefix="research-mcp-") as directory:
        config = Path(directory) / "config.json"
        config.write_text(json.dumps(server_config(settings)), encoding="utf-8")
        params = StdioServerParameters(
            command=command,
            args=[
                "--yes",
                settings.playwright_mcp_package,
                "--config",
                str(config),
                "--no-webmcp",
                "--image-responses",
                "omit",
                "--codegen",
                "none",
                "--output-dir",
                directory,
                "--timeout-navigation",
                "60000",
            ],
            cwd=directory,
        )
        async with Client(params, read_timeout_seconds=settings.tool_timeout) as client:
            discovered = []
            cursor = None
            while True:
                page = await client.list_tools(cursor=cursor)
                discovered.extend(page.tools)
                cursor = page.next_cursor
                if cursor is None:
                    break
            registry = ToolRegistry(discovered)
            if not {"browser_navigate", "browser_snapshot"} <= registry.enabled.keys():
                raise RuntimeError("Playwright MCP is missing required browser tools.")
            yield client, registry
        # SDK closes stdin, waits, and escalates to process-tree termination if needed.
