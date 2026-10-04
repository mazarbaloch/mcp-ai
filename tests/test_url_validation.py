import pytest

from app.config import Settings, validate_public_url


@pytest.mark.parametrize(
    "url",
    [
        "https://example.org/path?q=one#two",
        "http://example.com",
        "https://www.hamk.fi/en/",
        "https://8.8.8.8/",
    ],
)
def test_public_urls(url):
    assert validate_public_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "file:///C:/private.txt",
        "javascript:alert(1)",
        "data:text/html,hello",
        "example.com",
        "https://",
        "https://example.com:bad",
        "https://example.com:0",
        "http://localhost/",
        "http://127.0.0.1",
        "http://[::1]/",
        "http://192.168.1.1/",
        "http://10.0.0.1/",
        "http://169.254.169.254/",
        "http://2130706433/",
        "http://0x7f000001/",
        "https://user:pass@example.org",
        "https://bad host.com/",
        "https://example.com\\@localhost",
        "https://private.local/",
        "https://localhost./",
        "https://-bad.com",
        "https://bad..com",
    ],
)
def test_rejected_urls(url):
    with pytest.raises(ValueError, match="public"):
        validate_public_url(url)


def test_settings_environment_and_headed_default(monkeypatch):
    assert Settings().playwright_headless is False
    assert Settings().max_tool_steps == 50
    monkeypatch.setenv("PLAYWRIGHT_HEADLESS", "true")
    monkeypatch.setenv("MAX_TOOL_STEPS", "7")
    assert Settings.from_env().playwright_headless is True
    assert Settings.from_env().max_tool_steps == 7


@pytest.mark.parametrize(
    "override",
    [
        {"ollama_host": "https://ollama.com"},
        {"ollama_host": "http://example.org"},
        {"playwright_mcp_package": "unofficial-browser"},
        {"max_tool_steps": 0},
        {"ollama_host": "http://user:secret@localhost:11434"},
    ],
)
def test_invalid_configuration(override):
    with pytest.raises(ValueError):
        Settings(**override)
