"""Business development report generator.

Run with: streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from bizdev import config
from bizdev.crew import AnalysisError, run_bizdev_analysis
from bizdev.report import configuration_summary, report_filename

STEP_ORDER = {
    "market": "Market analysis",
    "tech": "Technology analysis",
    "bd": "Business development plan",
}

EXAMPLE = "bamboo home decor"

st.set_page_config(page_title="Business Development Report", page_icon="📊", layout="centered")


def render_sidebar() -> None:
    with st.sidebar:
        st.header("How it works")
        st.markdown(
            "A CrewAI crew of three agents runs in sequence. Each one owns one section of a "
            "single report:\n\n"
            "1. **Market Research** — size, segments, competitors, demand\n"
            "2. **Technology** — build/source approach, costs, risks, path to launch\n"
            "3. **Business Development** — positioning, pricing, GTM, 90-day plan\n\n"
            "Agents research with Google via Serper, then hand their findings to the next agent."
        )

        st.header("Configuration")
        for label, value in configuration_summary():
            st.text(f"{label}: {value}")

        st.header("API keys")
        status = config.env_status()
        for name, present in status.items():
            st.text(f"{'✅' if present else '❌'} {name}")
        if not all(status.values()):
            st.caption("Add missing keys to the .env file in the project root, then restart the app.")


def render_steps(box, completed: set[str]) -> None:
    box.markdown(
        "\n".join(
            f"- {'✅' if key in completed else '⏳'} {label}" for key, label in STEP_ORDER.items()
        )
    )


def run_analysis(product: str) -> None:
    completed: set[str] = set()

    with st.status("Starting crew…", expanded=True) as status:
        steps_box = st.empty()
        render_steps(steps_box, completed)

        def on_step(key: str, label: str) -> None:
            completed.add(key)
            render_steps(steps_box, completed)
            status.update(label=f"Completed: {label.lower()}")

        result = run_bizdev_analysis(product, on_step=on_step)
        completed.update(STEP_ORDER)
        render_steps(steps_box, completed)
        status.update(label="Analysis complete", state="complete")

    st.session_state["result"] = result


def render_result(result) -> None:
    st.markdown(result.report_markdown)

    meta = result.meta
    cols = st.columns(4)
    cols[0].metric("Words", f"{result.total_words:,}")
    cols[1].metric("Web searches", meta.searches_used if meta else 0)
    cols[2].metric("Duration", f"{meta.duration_seconds:.0f}s" if meta else "–")
    cols[3].metric("Sections", f"{sum(1 for v in result.raw_sections.values() if v.strip())}/3")

    st.divider()
    st.download_button(
        "Download report (.md)",
        data=result.report_markdown.encode("utf-8"),
        file_name=report_filename(result.product, "md"),
        mime="text/markdown",
        use_container_width=True,
    )

    with st.expander("Raw agent output"):
        for key, label in STEP_ORDER.items():
            raw = result.raw_sections.get(key, "")
            st.markdown(f"**{label}** — {len(raw.split()):,} words")
            st.code(raw or "(empty)", language="markdown")
            if key != "bd":
                st.divider()


def main() -> None:
    render_sidebar()

    st.title("📊 Business Development Report")
    st.caption(
        "Enter a product name or business idea. Three AI agents research it from different "
        "angles and produce one combined report."
    )

    missing = config.missing_keys()
    if missing:
        st.error(
            f"Missing API key(s): {', '.join(missing)}. "
            "Copy `.env.example` to `.env`, fill in the keys, then restart the app."
        )
        return

    with st.form("analysis_form", clear_on_submit=False):
        product = st.text_input(
            "Product or business idea",
            placeholder=EXAMPLE,
            max_chars=200,
        )
        submitted = st.form_submit_button("Generate report", type="primary", use_container_width=True)

    st.caption(
        "A run takes roughly 1-2 minutes and uses up to "
        f"{config.DEFAULT_MAX_SEARCHES_PER_AGENT * 3} Serper queries. "
        "Serper's free tier is a one-time allowance, so runs are budgeted."
    )

    if submitted:
        if not product.strip():
            st.warning("Enter a product name or business idea first.")
        else:
            try:
                run_analysis(product)
            except AnalysisError as exc:
                st.error(str(exc))

    result = st.session_state.get("result")
    if result is not None:
        st.divider()
        render_result(result)


if __name__ == "__main__":
    main()
