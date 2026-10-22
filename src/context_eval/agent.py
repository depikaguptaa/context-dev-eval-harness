"""Deep-research agent over the Context.dev API, built with LangGraph.

Flow: plan -> web_search -> read_pages -> synthesize -> done.

Every node logs through the Observer (latency, credits, status per step),
so a full run produces a cost/quality trace, not just an answer.

The synthesizer is intentionally extractive (keyword-overlap sentence
ranking) so the whole pipeline runs with no LLM key: the demo stays at
$0 on top of Context.dev's free tier. To use an LLM, swap
_extractive_summary for a model call; the graph shape does not change.
"""

from __future__ import annotations

import re
import time
from typing import TypedDict

from langgraph.graph import StateGraph, END

from .client import ContextDevClient, ContextDevError
from .observability import Observer


class ResearchState(TypedDict, total=False):
    question: str
    queries: list[str]
    search_results: list[dict]
    pages: list[dict]
    answer: str
    notes: list[str]


def _top_sentences(markdown: str, query_terms: set[str], k: int = 5) -> list[str]:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", markdown) if s.strip()]
    scored = []
    for s in sentences:
        words = set(re.findall(r"[a-zA-Z\u0900-\u0D7F]+", s.lower()))
        overlap = len(words & query_terms)
        if overlap and len(s) > 40:
            scored.append((overlap, s))
    scored.sort(key=lambda x: (-x[0], len(x[1])))
    seen: set[str] = set()
    out = []
    for _, s in scored:
        if s not in seen:
            seen.add(s)
            out.append(s)
        if len(out) == k:
            break
    return out


def build_research_agent(client: ContextDevClient, observer: Observer):
    """Return a compiled LangGraph app. Nodes close over client + observer."""

    def plan(state: ResearchState) -> ResearchState:
        question = state["question"]
        terms = [t for t in re.findall(r"[a-zA-Z\u0900-\u0D7F]{4,}", question.lower())]
        # Keep it simple and explainable: the raw question plus the two
        # longest content terms as focused queries.
        focused = sorted(set(terms), key=len, reverse=True)[:2]
        queries = [question] + [f"{question} {t}" for t in focused if t not in question.lower()]
        return {"queries": queries[:3], "notes": [f"planned {min(len(queries), 3)} queries"]}

    def web_search(state: ResearchState) -> ResearchState:
        results = []
        notes = list(state.get("notes", []))
        for q in state["queries"]:
            started = time.perf_counter()
            try:
                call = client.search(q, num_results=5)
                payload = call.payload
                items = payload.get("results", []) if isinstance(payload, dict) else []
                results.extend(items)
                observer.record("search", q, call.latency_ms, call.status,
                                credits=call.credits, notes=f"{len(items)} results")
            except ContextDevError as exc:
                observer.record("search", q, (time.perf_counter() - started) * 1000,
                                status=exc.status, ok=False, notes=str(exc)[:200])
                notes.append(f"search failed for {q!r}: {exc.error_code}")
        return {"search_results": results, "notes": notes}

    def read_pages(state: ResearchState) -> ResearchState:
        pages = []
        notes = list(state.get("notes", []))
        seen_urls: set[str] = set()
        for item in state.get("search_results", []):
            url = item.get("url") if isinstance(item, dict) else None
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            if len(pages) >= 3:
                break
            started = time.perf_counter()
            try:
                call = client.scrape(url, formats={"markdown": True},
                                     shared_params={"mainContentOnly": True})
                md = (call.payload.get("markdown") or {}).get("data") or ""
                pages.append({"url": url, "markdown": md,
                              "title": (call.payload.get("metadata") or {}).get("title", "")})
                observer.record("scrape", url, call.latency_ms, call.status,
                                credits=call.credits, notes=f"{len(md)} chars markdown")
            except ContextDevError as exc:
                observer.record("scrape", url, (time.perf_counter() - started) * 1000,
                                status=exc.status, ok=False, notes=str(exc)[:200])
                notes.append(f"scrape failed for {url}: {exc.error_code}")
        return {"pages": pages, "notes": notes}

    def synthesize(state: ResearchState) -> ResearchState:
        query_terms = set(re.findall(r"[a-zA-Z\u0900-\u0D7F]{4,}",
                                     state["question"].lower()))
        bullets = []
        for page in state.get("pages", []):
            for s in _top_sentences(page.get("markdown", ""), query_terms):
                bullets.append(f"- {s}  (source: {page.get('url')})")
        answer = "\n".join(bullets[:8]) or "No supporting sentences extracted."
        observer.record("synthesize", state["question"], 0.0, None, credits=0,
                        notes=f"{len(bullets)} evidence bullets, extractive (no LLM)")
        return {"answer": answer}

    graph = StateGraph(ResearchState)
    graph.add_node("plan", plan)
    graph.add_node("web_search", web_search)
    graph.add_node("read_pages", read_pages)
    graph.add_node("synthesize", synthesize)
    graph.set_entry_point("plan")
    graph.add_edge("plan", "web_search")
    graph.add_edge("web_search", "read_pages")
    graph.add_edge("read_pages", "synthesize")
    graph.add_edge("synthesize", END)
    return graph.compile()
