from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.ollama_client import check_model


def client_for(names):
    return AsyncMock(
        list=AsyncMock(
            return_value=SimpleNamespace(models=[SimpleNamespace(model=n) for n in names])
        ),
        show=AsyncMock(
            return_value=SimpleNamespace(
                capabilities=["tools"],
                modelinfo={"general.parameter_count": 9000000000},
            )
        ),
    )


async def test_available_model():
    assert "Available locally" in await check_model(client_for(["qwen3.5:9b"]), "qwen3.5:9b")


async def test_missing_model():
    with pytest.raises(RuntimeError, match="ollama pull qwen3.5:9b"):
        await check_model(client_for([]), "qwen3.5:9b")


async def test_offline():
    client = client_for([])
    client.list.side_effect = ConnectionError("offline")
    with pytest.raises(RuntimeError, match="ollama serve"):
        await check_model(client, "qwen3.5:9b")


async def test_remote_model_rejected():
    client = client_for(["cloud"])
    client.show.return_value = SimpleNamespace(modelinfo={})
    with pytest.raises(RuntimeError, match="cloud-backed"):
        await check_model(client, "cloud")
