import pytest


def test_only_allowed_discovered_tools(registry):
    names = {tool["function"]["name"] for tool in registry.ollama_tools()}
    assert names == {"browser_navigate", "browser_find", "browser_snapshot"}
    assert "browser_evaluate" in registry.discovered
    assert "browser_click" not in names  # Allowlisted but not discovered in this fixture.


@pytest.mark.parametrize(
    ("name", "arguments", "message"),
    [
        ("browser_evaluate", {}, "disabled"),
        ("shell", {}, "Unknown"),
        ("browser_navigate", {}, "Invalid"),
        ("browser_navigate", {"url": 123}, "Invalid"),
        ("browser_navigate", {"url": "file:///secret"}, "public"),
        ("browser_snapshot", {"filename": "../../secret"}, "disabled"),
        ("browser_snapshot", {"extra": True}, "Unexpected"),
        ("browser_snapshot", [], "JSON object"),
    ],
)
def test_rejects_unsafe_or_invalid_calls(registry, name, arguments, message):
    with pytest.raises(ValueError, match=message):
        registry.validate(name, arguments)
