# Context.dev eval harness

A typed Python client for the Context.dev web-data API, per-call
observability, a LangGraph research agent, and an eval probe set that checks
extraction quality, including Hindi and Tamil script coverage on Indic news
pages.

## Why this exists

Context.dev (YC S26) sells one API for live web data to AI agents. Their
founder's open ask on the YC page: "If you're building an AI product that
needs internet data at scale, please reach out." This repo is the answer to
that ask: an independent eval of their scrape API, built the way I'd build
eval infra on their team.

## Layout

- `src/context_eval/client.py` - typed client over POST /web/scrape,
  /web/search, /web/answers. Surfaces latency and credits_consumed per call.
- `src/context_eval/observability.py` - per-call JSONL trace (operation,
  target, latency, status, credits). Summarizes cost and quality per run.
- `src/context_eval/agent.py` - LangGraph research agent
  (plan, search, read pages, synthesize). Extractive synthesizer, so it runs
  with no LLM key.
- `src/context_eval/probes.py` - probe runner. Expectations are hypotheses,
  checked against real responses, never asserted conclusions.
- `probes/probe_set.yaml` - 9 live probes: English baselines, Indic script
  coverage, localized search, one failure-mode probe.
- `mock_server.py` - local mock of the API shapes for offline tests and demos.
- `run_live.py` - runs the probe set against the real API, writes a JSON
  report to `reports/`.

## Run it

```bash
python3 -m venv venv && venv/bin/pip install -r requirements.txt
venv/bin/python -m pytest tests/ -q        # 12 tests, against the mock + unit level
export CONTEXT_DEV_API_KEY=<free key>      # free tier, no card
venv/bin/python run_live.py                # ~9 calls, JSON report in reports/
```

## Verified facts

- Context.dev, YC S26, raised a $9M seed led by General Catalyst, announced
  by founder Yahia Bakour on 2026-10-19 (company blog, Dealroom, Runtimewire).
- API base https://api.context.dev/v1; endpoints /web/scrape, /web/search,
  /web/answers; request shapes verified against their public docs.
- No jobs posted on their YC page as of 2026-10-21
  (ycombinator.com/companies/contextdev/jobs).
- Founder contact published on the YC page: yahia@context.dev and
  https://link.context.dev/chat.

## Live results (2026-10-22)

- Full probe set run against the real API: 9/9 probes passed, 9 credits.
  The Hindi (BBC, Jagran) and Tamil (DailyThanthi) pages came back in their
  original script, and the 404 probe surfaced the documented failure
  contract (an output with success=false and error_code NOT_FOUND).
- The research agent was also run live end to end: 1 search, 3 page reads,
  an extractive answer with sources, 4 credits, full trace recorded.

## Honest gaps

- The /web/answers client method is covered for request shape against the
  mock only. The probes and the agent use scrape and search, so answers has
  never been called live.
- Run reports (reports/*.json) stay local and are not part of this repo.
