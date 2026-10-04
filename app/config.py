"""Configuration is local and needs no API keys or .env file."""

import ipaddress
import os
import re
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator


def validate_public_url(value: str) -> str:
    value = value.strip()
    try:
        url = urlsplit(value)
        host = url.hostname
        if (
            url.scheme not in {"http", "https"}
            or not host
            or url.username is not None
            or url.password is not None
            or url.port == 0
            or re.search(r"[\s\\\x00-\x1f\x7f]", value)
            or "%" in host
        ):
            raise ValueError
        host = host.rstrip(".").lower()
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            raise ValueError
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            # Disallow single-label and alternate numeric forms of loopback addresses.
            labels = host.encode("idna").decode().split(".")
            if len(labels) < 2 or not any(c.isalpha() for c in labels[-1]):
                raise ValueError from None
            if any(
                not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?", s) for s in labels
            ):
                raise ValueError from None
        else:
            if not address.is_global:
                raise ValueError
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Use a public http:// or https:// URL, without credentials.") from exc
    return value


class Settings(BaseModel):
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:9b"
    ollama_num_ctx: int = Field(default=32768, ge=8192, le=131072)
    playwright_mcp_package: str = "@playwright/mcp@0.0.83"
    playwright_headless: bool = False
    max_tool_steps: int = Field(default=20, ge=1, le=20)
    model_timeout: float = Field(default=300, ge=1, le=1800)
    tool_timeout: float = Field(default=90, ge=1, le=300)
    result_max_chars: int = Field(default=14000, ge=1000, le=30000)

    @field_validator("ollama_host")
    @classmethod
    def local_ollama_only(cls, value: str) -> str:
        url = urlsplit(value)
        if url.scheme != "http" or url.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("OLLAMA_HOST must use HTTP on the local loopback interface.")
        if url.username or url.password or url.query or url.fragment or url.path not in {"", "/"}:
            raise ValueError("OLLAMA_HOST must be a plain local origin.")
        return value

    @field_validator("playwright_mcp_package")
    @classmethod
    def official_pinned_package(cls, value: str) -> str:
        if not re.fullmatch(r"@playwright/mcp@\d+\.\d+\.\d+", value):
            raise ValueError("Use a pinned official @playwright/mcp@x.y.z package.")
        return value

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            **{
                name: os.environ[name.upper()]
                for name in cls.model_fields
                if name.upper() in os.environ
            }
        )
