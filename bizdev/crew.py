"""Build and run the sequential business development crew."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import datetime, timezone

from crewai import Crew, Process

from . import config
from .agents import build_agents
from .report import AnalysisResult, RunMeta, assemble_report
from .tasks import STEP_LABELS, build_tasks
from .tools import serper

logger = logging.getLogger(__name__)

_SECTION_KEYS = ["market", "tech", "bd"]


class AnalysisError(RuntimeError):
    """Raised when a run fails, with a message safe to show in the UI."""


def _count_searches(agents) -> int:
    total = 0
    for agent in agents:
        for tool in getattr(agent, "tools", []) or []:
            total += int(getattr(tool, "calls_used", 0) or 0)
    return total


def build_crew(product: str, on_step: Callable[[str, str], None] | None = None):
    """Build agents, context-chained tasks, and the sequential crew."""
    agents = build_agents()
    tasks = build_tasks(product, agents, on_step=on_step)

    crew = Crew(
        agents=agents,
        tasks=tasks,
        process=Process.sequential,
        memory=False,
        verbose=False,
        max_rpm=config.MAX_RPM,
    )
    return crew, tasks, agents


def run_bizdev_analysis(
    product: str,
    on_step: Callable[[str, str], None] | None = None,
) -> AnalysisResult:
    """Run all three agents and return the assembled report.

    ``on_step(key, label)`` fires as each task completes, where key is one of
    'market', 'tech', 'bd'.
    """
    product = product.strip()
    if not product:
        raise AnalysisError("Enter a product name or business idea first.")

    missing = config.missing_keys()
    if missing:
        raise AnalysisError(
            f"Missing API key(s) in .env: {', '.join(missing)}. Add them and restart the app."
        )

    # The cache exists to dedupe repeated queries within a run, not to serve stale
    # results to a later run, so it is cleared each time.
    serper._CACHE.clear()

    started = datetime.now(timezone.utc)
    timer = time.perf_counter()

    # Named differently from the parameter so the closure forwards instead of
    # recursing into itself.
    def notify(key: str, label: str) -> None:
        if on_step is not None:
            on_step(key, label)

    crew, tasks, agents = build_crew(product, on_step=notify)

    try:
        crew.kickoff()
    except Exception as exc:  # noqa: BLE001 - surfaced to the user as a friendly message
        logger.exception("Crew run failed for %r", product)
        raise AnalysisError(_friendly_error(exc)) from exc

    duration = time.perf_counter() - timer

    sections: dict[str, str] = {}
    for key, task in zip(_SECTION_KEYS, tasks, strict=True):
        output = getattr(task, "output", None)
        sections[key] = (getattr(output, "raw", "") or "") if output else ""

    empty = [STEP_LABELS[key] for key in _SECTION_KEYS if not sections.get(key, "").strip()]
    if len(empty) == len(_SECTION_KEYS):
        raise AnalysisError("The crew finished but produced no content. Check the API keys and try again.")

    meta = RunMeta(
        product=product,
        model_research=config.RESEARCH_MODEL,
        model_writer=config.WRITER_MODEL,
        searches_used=_count_searches(agents),
        search_budget=config.DEFAULT_MAX_SEARCHES_PER_AGENT,
        duration_seconds=duration,
        started_at=started,
    )

    return AnalysisResult(
        product=product,
        report_markdown=assemble_report(product, sections, meta),
        raw_sections=sections,
        meta=meta,
    )


def _friendly_error(exc: Exception) -> str:
    """Map low-level failures to something actionable."""
    name = type(exc).__name__
    text = str(exc)

    if "AuthenticationError" in name or "401" in text:
        return "OpenAI rejected the API key. Check OPENAI_API_KEY in your .env file."
    if "RateLimitError" in name or "rate limit" in text.lower():
        return "OpenAI rate limit reached. Wait a moment and try again."
    if "APIConnectionError" in name:
        return "Could not reach the OpenAI API. Check your network connection and try again."
    if "AgentToolsUsageError" in name:
        return "An agent tried to use a tool incorrectly. Try rephrasing the product input."
    return f"The crew run failed ({name}). Check the terminal logs for the full traceback."
