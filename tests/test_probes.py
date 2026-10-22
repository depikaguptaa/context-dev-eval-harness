"""Error-contract expectations: a failure-mode probe passes when the API
fails the way the docs promise, on either error surface (a per-output
success=false carrying the error code, or an HTTP error with the same code).
"""

from context_eval.client import CallResult, ContextDevError
from context_eval.observability import Observer
from context_eval.probes import _check_scrape, run_probes

PROBE = {
    "id": "scrape-404-page",
    "operation": "scrape",
    "target": "https://example.com/this-page-does-not-exist-xyz",
    "expect": {"min_chars": 0, "error_code": "NOT_FOUND"},
}


def test_output_level_error_contract_passes():
    payload = {"markdown": {"success": False, "data": None, "error_code": "NOT_FOUND"}}
    assert _check_scrape(PROBE, payload) == []


def test_output_level_wrong_error_code_fails():
    payload = {"markdown": {"success": False, "data": None, "error_code": "TIMEOUT"}}
    failures = _check_scrape(PROBE, payload)
    assert failures and "NOT_FOUND" in failures[0]


def test_output_level_unexpected_success_fails():
    payload = {"markdown": {"success": True, "data": "# hi", "error_code": None}}
    failures = _check_scrape(PROBE, payload)
    assert failures and "succeeded" in failures[0]


class _RaisingClient:
    def scrape(self, target, **kwargs):
        raise ContextDevError(400, "NOT_FOUND", {"error_code": "NOT_FOUND"})


def test_http_level_error_contract_passes():
    results = run_probes(_RaisingClient(), [PROBE], Observer())
    assert results[0]["ok"] is True
    assert results[0]["failures"] == []


class _OkClient:
    def scrape(self, target, **kwargs):
        return CallResult(
            operation="scrape", target=target, latency_ms=1.0, status=200,
            credits=1,
            payload={"markdown": {"success": False, "data": None,
                                  "error_code": "NOT_FOUND"}},
        )


def test_output_level_contract_passes_through_runner():
    results = run_probes(_OkClient(), [PROBE], Observer())
    assert results[0]["ok"] is True
