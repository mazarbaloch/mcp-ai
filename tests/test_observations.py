from app.observations import bound_history, compact, observed_pages


def test_compaction_keeps_complete_relevant_references():
    text = (
        "- Page URL: https://example.org/\n"
        + "\n".join(f'- link "Unrelated {i}" [ref=e{i}]:\n  - /url: /item/{i}' for i in range(200))
        + '\n- heading "Special topic" [ref=e999]\n- link "Special details" [ref=e1000]'
    )
    result = compact(text, 1200, "Special topic")
    assert len(result) <= 1200
    assert "[ref=e999]" in result
    assert "[ref=e1000]" in result
    assert "Observation shortened" in result
    assert "https://example.org/" in result


def test_only_page_metadata_is_a_visit():
    assert observed_pages("- Page URL: https://example.org/\n- /url: https://other.org/") == [
        "https://example.org/",
    ]


def test_history_budget_preserves_tool_pairs():
    messages = [{"role": "system", "content": "task"}]
    for _ in range(8):
        messages += [
            {"role": "assistant", "tool_calls": [{"function": {"name": "find"}}]},
            {"role": "tool", "content": "evidence\n" * 2000},
        ]
    assert bound_history(messages, [], 32768, "evidence")
    assert len(messages) == 17
    assert any("shortened" in m.get("content", "") for m in messages)
