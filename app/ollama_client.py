"""The model chooses tools; it never talks to Playwright itself."""

from contextlib import asynccontextmanager

from ollama import AsyncClient

from app.config import Settings


async def check_model(client: AsyncClient, model: str) -> str:
    try:
        response = await client.list()
    except Exception as exc:
        raise RuntimeError(
            "Ollama is unavailable. Start the Ollama app or run `ollama serve`."
        ) from exc
    available = {item.model for item in response.models}
    if model not in available:
        raise RuntimeError(f"Model {model!r} is not installed. Run `ollama pull {model}`.")
    details = await client.show(model)
    # SDK 0.6.2 discards newer remote_host fields; require local weight metadata instead.
    if not details.modelinfo or not details.modelinfo.get("general.parameter_count"):
        raise RuntimeError("This demo requires a local model; cloud-backed models are disabled.")
    if details.capabilities and "tools" not in details.capabilities:
        raise RuntimeError(f"Model {model!r} does not support tool calls.")
    return f"Available locally: {model}"


class LocalModel:
    def __init__(self, client: AsyncClient, settings: Settings):
        self.client = client
        self.settings = settings

    async def chat(self, messages: list[dict], tools: list[dict]):
        response = await self.client.chat(
            model=self.settings.ollama_model,
            messages=messages,
            tools=tools,
            think=False,
            options={
                "num_ctx": self.settings.ollama_num_ctx,
                "temperature": 0,
                "presence_penalty": 0,
                "num_predict": 4096,
            },
        )
        # Never store or display the separate thinking field.
        return response.message.model_dump(exclude={"thinking"}, exclude_none=True)


@asynccontextmanager
async def connect_ollama(settings: Settings):
    async with AsyncClient(host=settings.ollama_host, timeout=settings.model_timeout) as client:
        status = await check_model(client, settings.ollama_model)
        yield LocalModel(client, settings), status
