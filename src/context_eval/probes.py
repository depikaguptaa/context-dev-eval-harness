"""Eval probe runner: scripted extraction-quality probes against the API.

Each probe names an operation (scrape/search), a target, and expectations.
Expectations are hypotheses to check on a live run, not conclusions:

  min_chars:       the markdown output should carry at least this much text
  script:         one of devanagari/tamil; the output should contain at
                  least min_script_chars characters in that Unicode script
  min_results:    for search probes, at least this many results
  error_code:     the probe targets a failure mode; it passes when the API
                  fails the way the docs promise (an output with
                  success=false and this error_code, or an HTTP error
                  carrying the same code)

The runner never asserts on the live web inside the shipped tests; the
tests below exercise it against the local mock server only.
"""

from __future__ import annotations

import time
from pathlib import Path

import yaml

from .client import ContextDevClient, ContextDevError
from .observability import Observer

SCRIPT_RANGES = {
    "devanagari": (0x0900, 0x097F),
    "tamil": (0x0B80, 0x0BFF),
}


def script_coverage(text: str, script: str) -> int:
    lo, hi = SCRIPT_RANGES[script]
    return sum(1 for ch in text if lo <= ord(ch) <= hi)


def load_probe_set(path: str | Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    probes = data.get("probes", [])
    assert isinstance(probes, list) and probes, "probe set must be a non-empty list"
    return probes


def _check_scrape(probe: dict, payload: dict) -> list[str]:
    failures: list[str] = []
    expect = probe.get("expect", {})
    output = (payload.get("markdown") or {}) if isinstance(payload, dict) else {}
    expected_error = expect.get("error_code")
    if expected_error:
        if output.get("success"):
            failures.append(f"expected error {expected_error} but the scrape succeeded")
        elif output.get("error_code") != expected_error:
            failures.append(
                f"expected error {expected_error}, got {output.get('error_code')}"
            )
        return failures
    if not output.get("success"):
        failures.append(
            f"markdown output not successful (error_code={output.get('error_code')})"
        )
        return failures
    text = output.get("data") or ""
    min_chars = expect.get("min_chars", 0)
    if len(text) < min_chars:
        failures.append(f"markdown has {len(text)} chars, expected >= {min_chars}")
    script = expect.get("script")
    if script:
        covered = script_coverage(text, script)
        if covered < expect.get("min_script_chars", 0):
            failures.append(
                f"only {covered} {script} chars, expected >= "
                f"{expect.get('min_script_chars', 0)}"
            )
    return failures


def run_probes(
    client: ContextDevClient, probes: list[dict], observer: Observer
) -> list[dict]:
    results = []
    for probe in probes:
        pid = probe["id"]
        op = probe["operation"]
        target = probe["target"]
        started = time.perf_counter()
        failures: list[str] = []
        try:
            if op == "scrape":
                call = client.scrape(target, formats={"markdown": True},
                                     shared_params={"mainContentOnly": True})
                failures = _check_scrape(probe, call.payload)
            elif op == "search":
                call = client.search(target, num_results=probe.get("num_results", 10))
                items = call.payload.get("results", []) if isinstance(call.payload, dict) else []
                if len(items) < probe.get("expect", {}).get("min_results", 1):
                    failures.append(f"got {len(items)} results, expected more")
            else:
                raise ValueError(f"unknown probe operation: {op}")
            latency = (time.perf_counter() - started) * 1000
            observer.record(op, target, latency, call.status,
                            credits=call.credits,
                            ok=not failures,
                            notes="; ".join(failures) or "all expectations met")
            results.append({"id": pid, "ok": not failures, "failures": failures,
                            "latency_ms": round(latency, 1), "credits": call.credits})
        except ContextDevError as exc:
            latency = (time.perf_counter() - started) * 1000
            expected_error = probe.get("expect", {}).get("error_code")
            if expected_error and exc.error_code == expected_error:
                observer.record(op, target, latency, exc.status,
                                ok=True,
                                notes=f"failed as documented ({exc.error_code})")
                results.append({"id": pid, "ok": True, "failures": [],
                                "latency_ms": round(latency, 1), "credits": None})
                continue
            observer.record(op, target, latency, exc.status, ok=False,
                            notes=f"{exc.error_code}: {str(exc)[:160]}")
            results.append({"id": pid, "ok": False,
                            "failures": [f"API error {exc.status} ({exc.error_code})"],
                            "latency_ms": round(latency, 1), "credits": None})
    return results
