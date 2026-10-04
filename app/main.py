"""A small Gradio UI; run with uv run python -m app.main."""

import asyncio
from contextlib import suppress
from copy import deepcopy
from dataclasses import asdict

import gradio as gr

from app.agent import run_agent
from app.config import Settings, validate_public_url
from app.errors import error_message
from app.mcp.playwright_client import connect_playwright
from app.models import ResearchState
from app.ollama_client import connect_ollama

DEFAULT_URL = "https://www.hamk.fi/en/"
DEFAULT_QUESTION = (
    "Find the Computer Applications bachelor's programme. Tell me its duration and number of "
    "credits, and find where I can see the current curriculum or module map."
)


def render(state: ResearchState):
    status = (
        f"{state.status}\nOllama: {state.ollama_status}\n"
        f"Model: {state.model}\nPlaywright MCP: {state.mcp_status}"
    )
    capabilities = {
        "discovered_count": len(state.discovered),
        "enabled_for_model": state.enabled,
        "discovered_but_not_enabled": [n for n in state.discovered if n not in state.enabled],
    }
    return (
        state.answer,
        status,
        [asdict(event) for event in state.activity],
        capabilities,
        "\n".join(state.visited),
    )


async def inspect_services(model_name: str):
    state = ResearchState(model=model_name.strip())
    try:
        settings = Settings.from_env().model_copy(update={"ollama_model": state.model})
        try:
            async with connect_ollama(settings) as (_, status):
                state.ollama_status = status
        except Exception as exc:
            state.ollama_status = error_message(exc)
        async with connect_playwright(settings) as (_, registry):
            state.discovered = list(registry.discovered)
            state.enabled = list(registry.enabled)
        state.mcp_status = "Ready (discovery verified; a fresh session opens for each research run)"
    except Exception as exc:
        state.mcp_status = f"Connection failed: {error_message(exc)}"
    return render(state)[1], render(state)[3]


async def research(starting_url: str, question: str, model_name: str):
    queue = asyncio.Queue()
    state = ResearchState(model=model_name.strip(), status="Connecting…")

    async def update(current):
        await queue.put(deepcopy(current))

    async def produce():
        # Keep all MCP context-manager enter/exit calls in this task. Gradio consumes
        # the generator in separate tasks; yielding inside an MCP context is unsafe.
        try:
            validate_public_url(starting_url)
            settings = Settings.from_env().model_copy(update={"ollama_model": state.model})
            async with connect_ollama(settings) as (model, status):
                state.ollama_status = status
                await update(state)
                async with connect_playwright(settings) as (client, registry):
                    state.mcp_status = "Connected over stdio"
                    state.discovered = list(registry.discovered)
                    state.enabled = list(registry.enabled)
                    await update(state)
                    await run_agent(
                        question, starting_url, model, client, registry, settings, state, update
                    )
            state.mcp_status = "Closed; browser and MCP subprocess released"
        except Exception as exc:
            state.status = "Error"
            state.answer = f"Research could not complete: {error_message(exc)}"
            state.mcp_status = "Disconnected"
        finally:
            await update(state)
            await queue.put(None)

    producer = asyncio.create_task(produce())
    try:
        yield render(state)
        while (current := await queue.get()) is not None:
            yield render(current)
    finally:
        if not producer.done():
            producer.cancel()
        with suppress(asyncio.CancelledError):
            await producer


def build_app() -> gr.Blocks:
    settings = Settings.from_env()
    with gr.Blocks(title="Local Web Research Assistant", analytics_enabled=False) as demo:
        gr.Markdown("# Local Web Research Assistant\nqwen3.5:9b · Ollama · Playwright MCP")
        gr.Markdown("Ask a question about a public website and watch the browser tools at work.")
        with gr.Row():
            url = gr.Textbox(label="Starting URL", value=DEFAULT_URL, scale=3)
            model = gr.Textbox(label="Local model", value=settings.ollama_model, scale=1)
        question = gr.Textbox(label="Research task", value=DEFAULT_QUESTION, lines=3)
        with gr.Row():
            submit = gr.Button("Research", variant="primary")
            refresh = gr.Button("Check connections")
        status = gr.Textbox(label="Status", interactive=False, lines=4)
        gr.Markdown("## Answer")
        answer = gr.Markdown(value="Your findings will appear here.")
        visited = gr.Textbox(label="Visited pages", interactive=False, lines=3)
        gr.Markdown("## MCP Tool Activity\nObservable calls and results; no hidden reasoning.")
        activity = gr.JSON(label="Playwright MCP calls", value=[])
        with gr.Accordion("MCP Capabilities", open=True):
            capabilities = gr.JSON(label="Actual server tools")
        submit.click(
            research,
            [url, question, model],
            [answer, status, activity, capabilities, visited],
            concurrency_limit=1,
            concurrency_id="browser",
        )
        refresh.click(
            inspect_services,
            [model],
            [status, capabilities],
            concurrency_limit=1,
            concurrency_id="browser",
        )
        demo.load(
            inspect_services,
            [model],
            [status, capabilities],
            concurrency_limit=1,
            concurrency_id="browser",
        )
    return demo


if __name__ == "__main__":
    build_app().queue(max_size=4).launch(server_name="127.0.0.1", share=False)
