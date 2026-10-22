"""Run the live probe set against the real Context.dev API.

Needs CONTEXT_DEV_API_KEY in the environment (free tier, no card).
Optional --base-url overrides the API base (used to smoke-test against the
local mock server: python run_live.py --base-url http://127.0.0.1:8899/v1).

Writes a JSON report to reports/live_<ts>.json and prints a summary table.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from context_eval import ContextDevClient, Observer
from context_eval.probes import load_probe_set, run_probes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--probes", default="probes/probe_set.yaml")
    args = parser.parse_args()

    client = ContextDevClient(base_url=args.base_url) if args.base_url else ContextDevClient()
    observer = Observer()
    probes = load_probe_set(args.probes)
    results = run_probes(client, probes, observer)

    ok = sum(1 for r in results if r["ok"])
    print(f"\n{ok}/{len(results)} probes passed\n")
    for r in results:
        status = "PASS" if r["ok"] else "FAIL"
        detail = "; ".join(r["failures"]) if r["failures"] else "all expectations met"
        print(f"[{status}] {r['id']}: {detail} "
              f"({r['latency_ms']} ms, credits={r['credits']})")

    summary = observer.summarize()
    print(f"\nsummary: {summary['calls']} calls, {summary['ok']} ok, "
          f"{summary['failed']} failed, {summary['credits_charged']} credits charged, "
          f"avg {summary['avg_latency_ms']} ms")

    out = Path("reports") / f"live_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"results": results, "summary": summary,
                               "trace": observer.records}, indent=2, ensure_ascii=False))
    print(f"report: {out}")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
