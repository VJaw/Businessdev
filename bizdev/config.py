"""Configuration and environment loading for the business development crew."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")

SERPER_BASE_URL = "https://google.serper.dev"
SERPER_SEARCH_ENDPOINT = f"{SERPER_BASE_URL}/search"
SERPER_TIMEOUT_SECONDS = 10

RESEARCH_MODEL = os.getenv("RESEARCH_MODEL", "gpt-4o-mini")
WRITER_MODEL = os.getenv("WRITER_MODEL", "gpt-4o")

MAX_RPM = int(os.getenv("MAX_RPM", "20"))

DEFAULT_MAX_RESULTS = int(os.getenv("SERPER_MAX_RESULTS", "8"))
DEFAULT_MAX_SEARCHES_PER_AGENT = int(os.getenv("MAX_SEARCHES_PER_AGENT", "4"))


def openai_api_key() -> str | None:
    value = os.getenv("OPENAI_API_KEY", "").strip()
    return value or None


def serper_api_key() -> str | None:
    value = os.getenv("SERPER_API_KEY", "").strip()
    return value or None


def missing_keys() -> list[str]:
    """Names of required environment variables that are unset. Values are never returned."""
    missing: list[str] = []
    if not openai_api_key():
        missing.append("OPENAI_API_KEY")
    if not serper_api_key():
        missing.append("SERPER_API_KEY")
    return missing


def env_status() -> dict[str, bool]:
    """Presence flags for the UI. Deliberately does not expose key values."""
    return {"OPENAI_API_KEY": bool(openai_api_key()), "SERPER_API_KEY": bool(serper_api_key())}
