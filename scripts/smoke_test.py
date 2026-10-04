"""Real external services. Run explicitly; never collected by normal CI."""

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path

from app.agent import run_agent
from app.config import Settings
from app.errors import error_message
from app.main import DEFAULT_QUESTION, DEFAULT_URL
from app.mcp.playwright_client import connect_playwright
from app.models import ResearchState
from app.ollama_client import connect_ollama


async def smoke(mode: str, headed: bool = False, report: str | None = None) -> int:
    settings = Settings.from_env().model_copy(update={"playwright_headless": not headed})
    state = ResearchState(model=settings.ollama_model)

    async def update(current):
        if current.activity:
            event = current.activity[-1]
            print(f"{current.status} | #{event.sequence} {event.tool}: {event.status}", flush=True)
        else:
            print(current.status, flush=True)

    try:
        async with connect_playwright(settings) as (client, registry):
            state.discovered = list(registry.discovered)
            state.enabled = list(registry.enabled)
            print("Discovered:", ", ".join(state.discovered), flush=True)
            print("Enabled:", ", ".join(state.enabled), flush=True)
            if mode == "mcp":
                for name, arguments in [
                    ("browser_navigate", {"url": "https://example.com"}),
                    ("browser_snapshot", {}),
                ]:
                    result = await client.call_tool(name, arguments)
                    text = "\n".join(b.text for b in result.content if b.type == "text")
                    if result.is_error or "Example Domain" not in text:
                        raise RuntimeError(f"{name} failed: {text}")
                    print(f"PASS {name}: {text[:1000]}", flush=True)
                state.completed = True
            else:
                url = DEFAULT_URL if mode == "hamk" else "https://example.com"
                question = (
                    DEFAULT_QUESTION
                    if mode == "hamk"
                    else (
                        "Open the starting URL using the browser. Inspect its content "
                        "and tell me its title and purpose."
                    )
                )
                async with connect_ollama(settings) as (model, status):
                    state.ollama_status = status
                    await run_agent(question, url, model, client, registry, settings, state, update)
                print(state.answer, flush=True)
                print("Visited:", state.visited, flush=True)
                if not state.completed or not state.activity or not state.visited:
                    raise RuntimeError(
                        "No completed model answer with real tool/page observations."
                    )
                if mode == "hamk":
                    if len(state.activity) < 2 or not any(
                        "hamk.fi" in page
                        and ("computer-applications" in page or "curricul" in page)
                        for page in state.visited
                    ):
                        raise RuntimeError("No relevant programme/curriculum page reached.")
                    print(
                        "Workflow passed. Review the report for factual grounding; "
                        "this check does not prove every answer claim."
                    )
        print(f"PASS {mode}: session exited cleanly", flush=True)
        return 0
    except Exception as exc:
        state.status = f"FAIL {mode}: {error_message(exc)}"
        print(state.status, flush=True)
        return 1
    finally:
        if report:
            destination = Path(report)
            destination.parent.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(
                destination.write_text,
                json.dumps(asdict(state), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["mcp", "ollama", "hamk"])
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--report", help="Optional local JSON evidence report (use .artifacts/)")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(smoke(args.mode, args.headed, args.report)))
