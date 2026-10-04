# Verification notes

These checks were run on Windows 11 on 4 October 2026 with Python 3.13.5, uv 0.12.18,
Node.js 24.21.0, npm/npx 11.19.0, Ollama 0.35.1, and the installed local `qwen3.5:9b`
model.

## Deterministic quality gates

```text
uv sync --frozen       Checked 74 packages
uv run ruff check .    All checks passed!
uv run ruff format --check .
                         25 files already formatted
uv run pytest -q       76 passed in 3.08s
```

The tests mock Ollama and MCP, so CI needs no model, Chromium GUI, or internet access.

## Real Playwright MCP smoke test

`uv run python -m scripts.smoke_test mcp` passed with `@playwright/mcp@0.0.83`.
The server was started through `npx` over stdio, `list_tools()` returned 25 tools,
`browser_navigate` reached `https://example.com`, `browser_snapshot` returned its
accessibility content, and the SDK closed the subprocess cleanly. The headed variant
also passed, confirming that visible Chromium is available. The normal configuration
uses `PLAYWRIGHT_HEADLESS=false`.

## Real Ollama smoke test

`uv run python -m scripts.smoke_test ollama` passed with the local `qwen3.5:9b` model.
The model received the discovered Playwright schemas, requested `browser_navigate` and
`browser_snapshot`, and produced a grounded answer about Example Domain. No hosted model
or API key was used.

## HAMK end-to-end attempt

The live scenario reached these observed pages through model-selected MCP calls:

- `https://www.hamk.fi/en/`
- `https://www.hamk.fi/en/search-study-options/`
- `https://www.hamk.fi/en/degree/computer-applications/`
- `https://hamk.opinto-opas.fi/home?lang=en`
- `https://hamk.opinto-opas.fi/curricula`

With the default `MAX_TOOL_STEPS=12`, one run completed with an answer reporting the
observed duration (`3 years 6 months`), credits (`210 ECTS credits`), and the explicit
Study Plan link. Another run reached the curriculum system and then stopped at the
configured step limit while requesting another action. That is expected bounded-agent
behavior and is shown in the UI rather than hidden.

The runtime contains no HAMK facts or HAMK route helpers. The smoke script checks that
the workflow reaches a relevant live page and produces observations; it does not assert
hard-coded programme facts. Websites and model decisions can change, so the answer must
always be reviewed against the displayed MCP observations.

## UI startup

`uv run python -m app.main` started the Gradio app at `http://127.0.0.1:7860/`. The UI
displayed local Ollama availability, discovered capabilities, six enabled tools, streamed
tool activity, a final answer, and visited pages. It binds to loopback and does not create
a public share link.
