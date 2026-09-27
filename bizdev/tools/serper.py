"""Serper.dev web search exposed as a CrewAI tool.

Deliberately hand-rolled rather than pulled from ``crewai-tools`` so the install
stays small: this is the only tool the crew needs.
"""

from __future__ import annotations

import logging
from typing import Any

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from .. import config

logger = logging.getLogger(__name__)

# Shared across tool instances so repeated queries within a run cost one call.
_CACHE: dict[tuple[str, int], str] = {}

_SNIPPET_LIMIT = 260


class SerperSearchInput(BaseModel):
    """Input schema for a single web search."""

    query: str = Field(..., description="A specific Google search query, e.g. 'bamboo cutting board wholesale suppliers'.")
    num: int = Field(8, ge=1, le=25, description="How many results to return. Keep it low (5-8) to stay within budget.")


def _truncate(text: str, limit: int = _SNIPPET_LIMIT) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _format_response(payload: dict[str, Any], query: str) -> str:
    lines: list[str] = [f'Search results for "{query}":']

    answer_box = payload.get("answerBox") or {}
    answer = answer_box.get("answer") or answer_box.get("snippet")
    if answer:
        lines.append(f"\nDirect answer: {_truncate(str(answer), 400)}")

    knowledge_graph = payload.get("knowledgeGraph") or {}
    kg_description = knowledge_graph.get("description")
    if kg_description:
        lines.append(f"\nBackground: {_truncate(str(kg_description), 400)}")

    organic = payload.get("organic") or []
    if organic:
        lines.append("")
        for index, item in enumerate(organic, start=1):
            title = _truncate(item.get("title", "Untitled"), 120)
            link = item.get("link", "")
            lines.append(f"{index}. {title}")
            if link:
                lines.append(f"   {link}")
            snippet = item.get("snippet")
            if snippet:
                lines.append(f"   {_truncate(snippet)}")

    people_also_ask = payload.get("peopleAlsoAsk") or []
    if people_also_ask:
        questions = [_truncate(item.get("question", ""), 120) for item in people_also_ask if item.get("question")]
        if questions:
            lines.append("\nRelated questions worth investigating:")
            lines.extend(f"- {question}" for question in questions)

    if len(lines) == 1:
        return f'No results found for "{query}". Try a broader or differently worded query.'

    return "\n".join(lines)


class SerperSearchTool(BaseTool):
    """Search Google via serper.dev and return compact, citable snippets."""

    name: str = "serper_web_search"
    description: str = (
        "Search the live web with Google and return titles, URLs and snippets. "
        "Use it to verify facts about a market, find real competitors, prices, suppliers, "
        "regulations or technology options. Make each query specific and keyword-focused "
        "rather than asking a full question. Prefer several narrow queries over one vague one."
    )
    args_schema: type[BaseModel] = SerperSearchInput

    max_results: int = config.DEFAULT_MAX_RESULTS
    max_searches: int = config.DEFAULT_MAX_SEARCHES_PER_AGENT
    calls_used: int = 0

    def reset(self) -> None:
        """Reset the per-agent search budget at the start of a run."""
        self.calls_used = 0

    def _run(self, query: str, num: int = 8) -> str:
        query = str(query or "").strip()
        if not query:
            return "Search error: the query was empty. Provide specific keywords."

        if self.calls_used >= self.max_searches:
            return (
                f"Search budget exhausted ({self.max_searches} searches used). "
                "No more searches are available for this section. Write the section now "
                "using only the information you already gathered, and clearly mark any "
                "figure you could not verify as an estimate."
            )

        num = max(1, min(int(num or self.max_results), self.max_results))
        cache_key = (query.lower(), num)

        if cache_key in _CACHE:
            return _CACHE[cache_key]

        api_key = config.serper_api_key()
        if not api_key:
            return "Search error: SERPER_API_KEY is not configured. Write the section from existing knowledge."

        self.calls_used += 1

        try:
            response = requests.post(
                config.SERPER_SEARCH_ENDPOINT,
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                json={"q": query, "num": num},
                timeout=config.SERPER_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            formatted = _format_response(response.json(), query)
        except requests.Timeout:
            logger.warning("Serper request timed out for query %r", query)
            return f"Search error: request timed out for \"{query}\". Continue without these results."
        except requests.HTTPError as exc:
            logger.warning("Serper HTTP error for query %r: %s", query, exc.response.status_code)
            status = exc.response.status_code if exc.response is not None else "unknown"
            if status in (401, 403):
                return "Search error: Serper rejected the API key. Write the section from existing knowledge."
            if status == 429:
                return "Search error: Serper rate limit or quota reached. Write the section from existing knowledge."
            return f"Search error: Serper returned HTTP {status}. Continue without these results."
        except requests.RequestException as exc:
            logger.warning("Serper request failed for query %r: %s", query, exc)
            return f"Search error: could not reach Serper ({type(exc).__name__}). Continue without these results."

        _CACHE[cache_key] = formatted
        return formatted
