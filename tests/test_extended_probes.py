"""Extended probes (2026-10-27): new scripts, max_chars / allow_error
expectations, and the shape of the extended probe set. All offline."""

from context_eval.client import CallResult, ContextDevError
from context_eval.observability import Observer
from context_eval.probes import (
    _check_scrape,
    load_probe_set,
    run_probes,
    script_coverage,
)
from pathlib import Path

PROBE_SET = Path(__file__).resolve().parent.parent / "probes" / "probe_set.yaml"


def test_script_coverage_bengali_and_telugu():
    assert script_coverage("আমি বাংলা", "bengali") == 8
    assert script_coverage("నేను తెలుగు", "telugu") == 10
    assert script_coverage("hello", "bengali") == 0
    assert script_coverage("नमस्ते", "telugu") == 0


def test_max_chars_short_output_passes():
    probe = {"id": "x", "expect": {"max_chars": 2000}}
    payload = {"markdown": {"success": True, "data": "short wall notice"}}
    assert _check_scrape(probe, payload) == []


def test_max_chars_long_output_fails():
    probe = {"id": "x", "expect": {"max_chars": 10}}
    payload = {"markdown": {"success": True, "data": "a" * 500}}
    failures = _check_scrape(probe, payload)
    assert failures and "expected <=" in failures[0]


def test_allow_error_output_level_failure_passes():
    probe = {"id": "x", "expect": {"allow_error": True}}
    payload = {"markdown": {"success": False, "data": None, "error_code": "FORBIDDEN"}}
    assert _check_scrape(probe, payload) == []


def test_allow_error_success_still_judged_by_max_chars():
    probe = {"id": "x", "expect": {"allow_error": True, "max_chars": 10}}
    payload = {"markdown": {"success": True, "data": "a" * 500}}
    assert _check_scrape(probe, payload)


class _RaisingClient:
    def scrape(self, target, **kwargs):
        raise ContextDevError(403, "FORBIDDEN", {"error_code": "FORBIDDEN"})


def test_allow_error_http_level_failure_passes():
    probe = {
        "id": "login-wall",
        "operation": "scrape",
        "target": "https://x.com/home",
        "expect": {"max_chars": 2000, "allow_error": True},
    }
    results = run_probes(_RaisingClient(), [probe], Observer())
    assert results[0]["ok"] is True
    assert results[0]["failures"] == []


class _OkClient:
    def scrape(self, target, **kwargs):
        return CallResult(
            operation="scrape", target=target, latency_ms=1.0, status=200,
            credits=1,
            payload={"markdown": {"success": True, "data": "wall " * 500}},
        )


def test_allow_error_long_success_fails_through_runner():
    probe = {
        "id": "login-wall",
        "operation": "scrape",
        "target": "https://x.com/home",
        "expect": {"max_chars": 2000, "allow_error": True},
    }
    results = run_probes(_OkClient(), [probe], Observer())
    assert results[0]["ok"] is False


def test_probe_set_loads_with_extended_ids():
    probes = load_probe_set(PROBE_SET)
    ids = [p["id"] for p in probes]
    assert len(probes) == 16
    assert len(ids) == len(set(ids))
    for wanted in (
        "bengali-news-anandabazar",
        "telugu-news-eenadu",
        "js-rendered-quotes",
        "long-form-wikipedia",
        "mixed-script-wikipedia",
        "search-hindi-query",
        "login-wall-x-home",
    ):
        assert wanted in ids
    for probe in probes:
        assert probe["operation"] in ("scrape", "search")
        assert probe["target"]
