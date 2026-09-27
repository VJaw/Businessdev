"""The three specialist agents.

Prompts are deliberately category-agnostic: the same three agents have to work
for a software product, a physical consumer good, or a service, so each agent is
told to classify the input first and then pick the metrics that fit.
"""

from __future__ import annotations

from crewai import Agent

from . import config
from .tools.serper import SerperSearchTool

SECTION_MARKET = "## 1. Market Analysis"
SECTION_TECH = "## 2. Technology Analysis"
SECTION_BD = "## 3. Business Development Strategy"


def _search_tool() -> SerperSearchTool:
    """Each agent gets its own tool instance so the search budget is per-agent."""
    return SerperSearchTool(
        max_results=config.DEFAULT_MAX_RESULTS,
        max_searches=config.DEFAULT_MAX_SEARCHES_PER_AGENT,
    )


def build_agents() -> list[Agent]:
    """Build a fresh set of agents. Tasks are bound to these instances."""
    market_researcher = Agent(
        role="Market Research Analyst",
        goal=(
            "Establish the commercial reality of a proposed product: how big the opportunity "
            "is, who buys it, who they buy it from today, and whether demand is real and growing."
        ),
        backstory=(
            "You have run category and competitive research for physical consumer brands and "
            "for B2B software companies. You are equally comfortable reading retail category "
            "reports and analysing software market landscapes. You are comfortable saying the "
            "market is smaller than the founder hopes, and you back every claim with a source."
        ),
        tools=[_search_tool()],
        llm=config.RESEARCH_MODEL,
        allow_delegation=False,
        verbose=False,
    )

    technology_analyst = Agent(
        role="Technology & Operations Analyst",
        goal=(
            "Work out what it would actually take to build, source, deliver and operate the "
            "product, and where the technical or operational risk sits."
        ),
        backstory=(
            "You have shipped both software products and physical products, and you know that "
            "'the technology' means very different things in each case. For software you think "
            "about architecture, integrations, data and security. For physical goods you think "
            "about materials, tooling, manufacturing, quality control, freight and shelf or "
            "platform constraints. You flag the expensive, slow-to-change decisions early."
        ),
        tools=[_search_tool()],
        llm=config.RESEARCH_MODEL,
        allow_delegation=False,
        verbose=False,
    )

    business_development_lead = Agent(
        role="Business Development Lead",
        goal=(
            "Turn the market and technology findings into a commercial plan: who to sell to, at "
            "what price, through which channel, in what order, and what would have to be true "
            "for this to work."
        ),
        backstory=(
            "You have taken products from first sale to repeat revenue in both software and "
            "consumer goods. You are comfortable with retail price bands, COGS and landed cost, "
            "and equally comfortable with seat-based pricing and sales cycles. You are direct "
            "about viability, and you always end with actions a founder could start on Monday."
        ),
        tools=[_search_tool()],
        llm=config.WRITER_MODEL,
        allow_delegation=False,
        verbose=False,
    )

    return [market_researcher, technology_analyst, business_development_lead]
