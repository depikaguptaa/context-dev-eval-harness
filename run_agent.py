"""Run the LangGraph research agent once and print the answer plus trace.

Needs CONTEXT_DEV_API_KEY in the environment (free tier, no card).
Optional --base-url overrides the API base (used to smoke-test against the
local mock server: python run_agent.py --base-url http://127.0.0.1:8899/v1).

Example:
    python run_agent.py "What is Context.dev and what does its API do?"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from context_eval import ContextDevClient, Observer, build_research_agent

DEFAULT_QUESTION = "What is Context.dev and what does its API do for AI agents?"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("question", nargs="?", default=DEFAULT_QUESTION)
    parser.add_argument("--base-url", default=None)
    args = parser.parse_args()

    client = ContextDevClient(base_url=args.base_url) if args.base_url else ContextDevClient()
    observer = Observer()
    app = build_research_agent(client, observer)

    print(f"question: {args.question}\n")
    out = app.invoke({"question": args.question})

    print("answer (extractive, with sources):")
    print(out.get("answer", "(no answer)"))

    print("\ntrace:")
    for r in observer.records:
        print(f"  {r['operation']:<10} {str(r['target'])[:64]:<64} "
              f"{r['latency_ms']} ms, status={r['status']}, credits={r['credits']}")

    summary = observer.summarize()
    print(f"\nsummary: {summary['calls']} calls, {summary['ok']} ok, "
          f"{summary['credits_charged']} credits charged, "
          f"avg {summary['avg_latency_ms']} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
