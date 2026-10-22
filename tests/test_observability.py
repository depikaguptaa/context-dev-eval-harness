"""Observer tests: JSONL records and summary math."""

import json

from context_eval import Observer


def test_record_writes_jsonl(tmp_path):
    log = tmp_path / "trace.jsonl"
    obs = Observer(log_path=log)
    obs.record("scrape", "https://example.com", 123.4, 200, credits=1,
               notes="ok")
    lines = log.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["operation"] == "scrape"
    assert record["target"] == "https://example.com"
    assert record["latency_ms"] == 123.4
    assert record["credits"] == 1
    assert record["ok"] is True


def test_summarize(tmp_path):
    obs = Observer(log_path=tmp_path / "t.jsonl")
    obs.record("scrape", "a", 100.0, 200, credits=1)
    obs.record("search", "b", 200.0, 200, credits=1)
    obs.record("scrape", "c", 300.0, 400, ok=False, notes="boom")
    summary = obs.summarize()
    assert summary["calls"] == 3
    assert summary["ok"] == 2
    assert summary["failed"] == 1
    assert summary["credits_charged"] == 2
    assert summary["by_operation"] == {"scrape": 2, "search": 1}
