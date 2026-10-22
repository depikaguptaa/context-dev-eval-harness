"""Client unit tests: request shapes, auth, and error semantics."""

import json

import pytest

from context_eval import ContextDevClient, ContextDevError, MissingApiKey


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("CONTEXT_DEV_API_KEY", raising=False)
    with pytest.raises(MissingApiKey):
        ContextDevClient()


def test_scrape_request_shape(monkeypatch, mock_base_url):
    seen = {}

    import context_eval.client as client_mod

    real_post = client_mod.requests.post

    def spy(url, headers=None, json=None, timeout=None):
        seen["url"] = url
        seen["headers"] = headers
        seen["json"] = json
        return real_post(url, headers=headers, json=json, timeout=timeout)

    monkeypatch.setattr(client_mod.requests, "post", spy)
    client = ContextDevClient(api_key="k", base_url=mock_base_url)
    result = client.scrape("https://example.com/hindi-news")

    assert seen["url"] == f"{mock_base_url}/web/scrape"
    assert seen["headers"]["Authorization"] == "Bearer k"
    # formats is an object of booleans, sharedParams is camelCase (per docs).
    assert seen["json"]["url"] == "https://example.com/hindi-news"
    assert seen["json"]["formats"] == {"markdown": True}
    assert seen["json"]["sharedParams"] == {"mainContentOnly": True}
    # Response shape mirrored by the mock.
    assert result.status == 200
    assert result.credits == 1
    assert result.payload["markdown"]["success"] is True


def test_search_request_shape(monkeypatch, mock_base_url):
    seen = {}
    import context_eval.client as client_mod

    real_post = client_mod.requests.post

    def spy(url, headers=None, json=None, timeout=None):
        seen["json"] = json
        return real_post(url, headers=headers, json=json, timeout=timeout)

    monkeypatch.setattr(client_mod.requests, "post", spy)
    client = ContextDevClient(api_key="k", base_url=mock_base_url)
    client.search("UPI autopay RBI", num_results=5, country="in")
    assert seen["json"]["query"] == "UPI autopay RBI"
    assert seen["json"]["numResults"] == 5
    assert seen["json"]["country"] == "in"


def test_answers_request_shape(monkeypatch, mock_base_url):
    seen = {}
    import context_eval.client as client_mod

    real_post = client_mod.requests.post

    def spy(url, headers=None, json=None, timeout=None):
        seen["url"] = url
        seen["json"] = json
        return real_post(url, headers=headers, json=json, timeout=timeout)

    monkeypatch.setattr(client_mod.requests, "post", spy)
    client = ContextDevClient(api_key="k", base_url=mock_base_url)
    result = client.answers("What are the plan names?",
                            json_format={"plans": [{"name": ""}]}, mode="fast")
    assert seen["url"] == f"{mock_base_url}/web/answers"
    assert seen["json"]["task"] == "What are the plan names?"
    assert seen["json"]["mode"] == "fast"
    assert seen["json"]["json_format"] == {"plans": [{"name": ""}]}
    assert result.payload["partial"] is False


def test_400_surfaces_error_code(client):
    with pytest.raises(ContextDevError) as exc_info:
        client.scrape("https://example.com/notfound-page")
    assert exc_info.value.status == 400
    assert exc_info.value.error_code == "NOT_FOUND"
