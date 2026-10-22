"""Thin typed client over the Context.dev REST API.

Endpoint shapes verified from https://docs.context.dev on 2026-10-21:

  scrape   POST /web/scrape
           {"url": ..., "formats": {"markdown": true}, "sharedParams": {"mainContentOnly": true}}
           Every output carries {requested, success, data}. Failed outputs have
           success=false, data=null, error_code and message.
  search   POST /web/search
           {"query": ..., "numResults": 10}  (also includeDomains, excludeDomains,
           freshness, country, languages). 1 credit per 10 results.
  answers  POST /web/answers
           {"mode": "fast", "task": ..., "json_format": {...}, "timeoutOpts": {...}}
           Response: {json_content, sources, partial}.

Auth:  Authorization: Bearer $CONTEXT_DEV_API_KEY
Base:  https://api.context.dev/v1
Free tier: 1,000 credits/month, no credit card (context.dev FAQ).

Usage reporting: the FAQ says to check key_metadata.credits_consumed for the
amount a request charged. The client surfaces it on every CallResult.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any

import requests

BASE_URL = "https://api.context.dev/v1"


class MissingApiKey(RuntimeError):
    """Raised when no API key is available and a live call is attempted."""


class ContextDevError(RuntimeError):
    """Raised for HTTP >= 400. Carries status, error_code and raw body."""

    def __init__(self, status: int, error_code: str | None, body: Any):
        self.status = status
        self.error_code = error_code
        self.body = body
        super().__init__(
            f"context.dev API error: HTTP {status} error_code={error_code}"
        )


@dataclass
class CallResult:
    operation: str
    target: str
    latency_ms: float
    status: int
    credits: int | None
    payload: dict = field(default_factory=dict)


def _safe_json(resp: requests.Response) -> dict:
    try:
        data = resp.json()
    except ValueError:
        return {"_raw": resp.text[:2000]}
    return data if isinstance(data, dict) else {"_raw": data}


def _error_code(payload: dict) -> str | None:
    code = payload.get("error_code")
    if isinstance(code, str):
        return code
    # Some errors nest the code one level down.
    for value in payload.values():
        if isinstance(value, dict) and isinstance(value.get("error_code"), str):
            return value["error_code"]
    return None


def _credits(payload: dict) -> int | None:
    meta = payload.get("key_metadata")
    if isinstance(meta, dict):
        value = meta.get("credits_consumed")
        if isinstance(value, (int, float)):
            return int(value)
    return None


class ContextDevClient:
    """Minimal client. Key comes from the env unless passed explicitly."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = BASE_URL,
        timeout: float = 60.0,
    ):
        key = api_key or os.environ.get("CONTEXT_DEV_API_KEY")
        if not key:
            raise MissingApiKey(
                "Set CONTEXT_DEV_API_KEY to run live calls "
                "(free tier: 1,000 credits/month, no card required), or pass "
                "api_key=. For offline runs, point base_url at mock_server.py."
            )
        self.api_key = key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _post(
        self, operation: str, target: str, path: str, body: dict
    ) -> CallResult:
        started = time.perf_counter()
        resp = requests.post(
            f"{self.base_url}{path}",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=self.timeout,
        )
        latency_ms = (time.perf_counter() - started) * 1000
        payload = _safe_json(resp)
        if resp.status_code >= 400:
            raise ContextDevError(resp.status_code, _error_code(payload), payload)
        return CallResult(
            operation=operation,
            target=target,
            latency_ms=latency_ms,
            status=resp.status_code,
            credits=_credits(payload),
            payload=payload,
        )

    def scrape(
        self,
        url: str,
        formats: dict | None = None,
        shared_params: dict | None = None,
        **extra: Any,
    ) -> CallResult:
        """One URL to Markdown/HTML/screenshot/structured fields. formats is a
        dict like {"markdown": True} (verified against the docs curl example)."""
        params = {"mainContentOnly": True}
        if shared_params:
            params.update(shared_params)
        body: dict[str, Any] = {
            "url": url,
            "formats": formats or {"markdown": True},
            "sharedParams": params,
        }
        body.update(extra)
        return self._post("scrape", url, "/web/scrape", body)

    def search(
        self,
        query: str,
        num_results: int = 10,
        country: str | None = None,
        languages: list[str] | None = None,
        **extra: Any,
    ) -> CallResult:
        """Web search. Field names per the published OpenAPI (numResults etc)."""
        body: dict[str, Any] = {"query": query, "numResults": num_results}
        if country:
            body["country"] = country
        if languages:
            body["languages"] = languages
        body.update(extra)
        return self._post("search", query, "/web/search", body)

    def answers(
        self,
        task: str,
        json_format: dict | None = None,
        mode: str = "fast",
        **extra: Any,
    ) -> CallResult:
        """Research task to structured JSON with sources."""
        body: dict[str, Any] = {"mode": mode, "task": task}
        if json_format:
            body["json_format"] = json_format
        body.update(extra)
        return self._post("answers", task, "/web/answers", body)
