"""The three sequential tasks, context-chained so each agent sees prior findings.

Sections are fixed and owned one-per-agent, so the report is assembled by simple
concatenation with no extra synthesis LLM call.
"""

from __future__ import annotations

from collections.abc import Callable

from crewai import Agent, Task

from . import config
from .agents import SECTION_BD, SECTION_MARKET, SECTION_TECH

STEP_LABELS = {
    "market": "Market analysis",
    "tech": "Technology analysis",
    "bd": "Business development plan",
}

_CLASSIFY_RULE = (
    "Before you analyse anything, silently classify what you have been given as one of: "
    "software/SaaS, hardware, physical consumer good, service/agency, marketplace, or "
    "consumer brand. Then use the metrics and channels that actually apply to that type. "
    "A physical good is sized by category retail spend, unit economics and channel margin; "
    "software is sized by number of paying accounts and ACV. Never force a software framing "
    "onto a physical product, or a retail framing onto software."
)

_EVIDENCE_RULE = (
    "Separate what you verified from what you inferred. Every number must either carry the "
    "source you found it in, or be explicitly labelled an estimate. If the search budget is "
    "exhausted or the web is thin on a point, write your best estimate and mark it "
    "'(unverified estimate)' rather than silently presenting a guess as fact. "
    "If you genuinely cannot find something, write 'not found in available sources'."
)

_STYLE_RULE = (
    "Write in markdown using sub-headings and bullets. Start your output with the exact line "
    "{heading} as a level-2 heading. Do not add a top-level title, do not repeat that heading, "
    "and do not write any other numbered section."
)


def _budget_note() -> str:
    return (
        f"You have a hard budget of {config.DEFAULT_MAX_SEARCHES_PER_AGENT} web searches for this "
        "entire section. Spend it on the highest-value unknowns, not on confirmations."
    )


def _market_description(product: str) -> str:
    return f"""Research the market for this product or business idea: {product}

{_CLASSIFY_RULE}

Cover:
- What the customer actually wants, and the job it does in their life or business.
- Market size, sized the way the product type demands, with a clear statement of what is
  measured and what is assumed. Show the arithmetic behind any estimate.
- The specific customer segments worth targeting, ranked, with why each would buy.
- The current competitive landscape: 4-6 named real competitors or substitutes, what each
  does well, what they charge, and the gap the new product could occupy.
- Demand signals: search interest, category growth rate, review volumes, seasonality,
  regulatory or cultural tailwinds and headwinds.
- The single strongest reason this could work, and the single strongest reason it might not.

{_budget_note()}
{_EVIDENCE_RULE}
{_STYLE_RULE.format(heading=SECTION_MARKET)}

Aim for 600-900 words."""


def _tech_description(product: str) -> str:
    return f"""Assess the technology and operational reality of this product: {product}

You are given the market research below as context. Use it, and do not repeat it.

{_CLASSIFY_RULE}

Cover, interpreting "technology" for the product type:
- The realistic build, source or production approach, and why it is the sensible one.
- Build versus buy versus partner, with a recommendation and the reasoning behind it.
- The specific components, services, suppliers, platforms or integrations involved, and
  roughly what each costs to get going.
- The technical or operational risks that could delay or sink a launch, each with a
  mitigation. For physical goods this means materials, tooling, MOQ, quality control,
  freight, duty and compliance; for software it means architecture, data, security and
  third-party dependencies.
- A realistic path to a first sale, then a path to scale, in ordered stages with rough
  effort and rough cost attached.
- One or two decisions that are expensive or slow to reverse, flagged as such.

{_budget_note()}
{_EVIDENCE_RULE}
{_STYLE_RULE.format(heading=SECTION_TECH)}

Aim for 600-900 words."""


def _bd_description(product: str) -> str:
    return f"""Write the business development and go-to-market plan for this product: {product}

You are given the market and technology analysis below as context. Use them and build on
them. You own the judgement in this report.

{_CLASSIFY_RULE}

Cover:
- A five-bullet executive summary, the first thing a reader sees: the opportunity, the
  biggest risk, the single most important next step, and a straight verdict on whether this
  is worth pursuing.
- Positioning: the single clearest description of what this is and who it is for, the wedge
  to enter through, and the message that would land with the priority segment.
- Pricing that reflects the product type: retail price bands and unit economics such as
  COGS, landed cost and gross margin for physical goods, or a pricing model and rationale
  for software or services. Include the unit economics arithmetic for physical products.
- The go-to-market: the 2-3 channels most likely to work for this product type and segment,
  why those rather than the obvious alternatives, and roughly what each costs or requires.
- Partnerships, suppliers or distribution relationships that would materially help.
- A 90-day plan: ordered phases with concrete deliverables, and what success looks like at
  day 30, 60 and 90.
- The top 3 risks to the business case with how to de-risk each, and the metrics that would
  prove the thesis right or wrong.

{_budget_note()}
{_EVIDENCE_RULE}
{_STYLE_RULE.format(heading=SECTION_BD)}

Aim for 900-1200 words."""


def build_tasks(
    product: str,
    agents: list[Agent],
    on_step: Callable[[str, str], None] | None = None,
) -> list[Task]:
    """Build the three tasks, chained via context.

    ``on_step(key, label)`` is invoked when a task completes.
    """
    market_agent, tech_agent, bd_agent = agents

    def make_callback(key: str):
        if on_step is None:
            return None

        def callback(output) -> None:
            on_step(key, STEP_LABELS[key])

        return callback

    market_task = Task(
        description=_market_description(product),
        expected_output=(
            f"Markdown starting with the level-2 heading '{SECTION_MARKET}', covering "
            "segmentation, a sized market with visible assumptions, named competitors, demand "
            "signals, and an honest best-case / worst-case."
        ),
        agent=market_agent,
        markdown=True,
        callback=make_callback("market"),
    )

    tech_task = Task(
        description=_tech_description(product),
        expected_output=(
            f"Markdown starting with the level-2 heading '{SECTION_TECH}', covering the "
            "build-or-source approach, a build-vs-buy call, real costs, ranked risks with "
            "mitigations, a staged path to first sale and to scale, and the costly-to-reverse "
            "decisions."
        ),
        agent=tech_agent,
        context=[market_task],
        markdown=True,
        callback=make_callback("tech"),
    )

    bd_task = Task(
        description=_bd_description(product),
        expected_output=(
            f"Markdown starting with the level-2 heading '{SECTION_BD}', containing a "
            "five-bullet executive summary, positioning, product-appropriate pricing with unit "
            "economics, prioritised go-to-market channels, partnership options, a phased "
            "90-day plan with 30/60/90 checkpoints, and the top risks with metrics."
        ),
        agent=bd_agent,
        context=[market_task, tech_task],
        markdown=True,
        callback=make_callback("bd"),
    )

    return [market_task, tech_task, bd_task]
