from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class Activity:
    sequence: int
    tool: str
    arguments: dict[str, Any]
    status: Literal["success", "error", "blocked"]
    duration_ms: int
    result_preview: str
    source: str = "Playwright MCP"


@dataclass
class ResearchState:
    answer: str = ""
    status: str = "Ready"
    ollama_status: str = "Not checked"
    mcp_status: str = "Not connected"
    model: str = ""
    discovered: list[str] = field(default_factory=list)
    enabled: list[str] = field(default_factory=list)
    activity: list[Activity] = field(default_factory=list)
    observations: list[str] = field(default_factory=list)
    visited: list[str] = field(default_factory=list)
    completed: bool = False
