"""Bound text while retaining complete reference-bearing lines and page metadata."""

import json
import re


def observed_pages(text: str) -> list[str]:
    # Only page metadata, never model arguments or arbitrary links in page content.
    return re.findall(r"^- Page URL: (https?://\S+)\s*$", text, re.MULTILINE)


def compact(text: str, limit: int, question: str = "") -> str:
    if len(text) <= limit:
        return text
    notice = "\n[Observation shortened. Use browser_find or browser_snapshot(target=...) for more.]"
    lines = text.splitlines()
    terms = {word.lower() for word in re.findall(r"\w{4,}", question)} - {
        "find",
        "tell",
        "where",
        "what",
        "this",
        "that",
        "with",
        "from",
        "about",
        "please",
    }
    frequency = {term: sum(term in line.lower() for line in lines) for term in terms}
    scores = []
    for index, line in enumerate(lines):
        score = (1000 if index < 12 else 0) + (8 if "heading " in line else 0)
        score += 3 if "[ref=" in line or "/url:" in line else 0
        # Repeated programme/product names should not crowd out rare requested details.
        score += sum(100 / frequency[term] for term in terms if term in line.lower())
        scores.append((score, index))
    selected = set()
    used = len(notice)
    for _, index in sorted(scores, key=lambda pair: (-pair[0], pair[1])):
        # Keep adjacent link URLs and element references together where possible.
        group = set(range(max(0, index - 1), min(len(lines), index + 3))) - selected
        size = sum(len(lines[i]) + 1 for i in group)
        if used + size <= limit:
            selected.update(group)
            used += size
    return "\n".join(lines[i] for i in sorted(selected)) + notice


def bound_history(messages: list[dict], tools: list[dict], num_ctx: int, question: str) -> bool:
    # Conservative byte budget, with room for the output and chat-template overhead.
    budget = (num_ctx - 4096) * 2

    def size():
        return len(json.dumps([messages, tools], ensure_ascii=False).encode("utf-8"))

    for message in messages:
        if size() <= budget:
            return True
        if message["role"] == "tool":
            message["content"] = compact(message["content"], 1400, question)
    return size() <= budget
