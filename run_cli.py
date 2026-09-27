"""Headless runner: python run_cli.py "bamboo home decor" """

from __future__ import annotations

import sys

from bizdev import config
from bizdev.crew import AnalysisError, run_bizdev_analysis


def main() -> int:
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print('Usage: python run_cli.py "product name or business idea"')
        return 2

    product = sys.argv[1].strip()
    missing = config.missing_keys()
    if missing:
        print(f"Missing API key(s) in .env: {', '.join(missing)}")
        print("Add them to .env (see .env.example) and try again.")
        return 2

    print(f"Analysing: {product}")
    print("-" * 60)

    def on_step(key: str, label: str) -> None:
        print(f"  [done] {label}")

    try:
        result = run_bizdev_analysis(product, on_step=on_step)
    except AnalysisError as exc:
        print(f"\nFailed: {exc}")
        return 1

    print("-" * 60)
    print(f"{result.total_words} words, {result.meta.searches_used} searches, {result.meta.duration_seconds:.0f}s\n")
    print(result.report_markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
