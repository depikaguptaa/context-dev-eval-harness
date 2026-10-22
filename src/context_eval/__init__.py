"""context_eval: eval harness + deep-research agent over the Context.dev API."""

from .client import ContextDevClient, ContextDevError, MissingApiKey, CallResult
from .observability import Observer
from .agent import build_research_agent
from .probes import load_probe_set, run_probes, script_coverage

__all__ = [
    "ContextDevClient",
    "ContextDevError",
    "MissingApiKey",
    "CallResult",
    "Observer",
    "build_research_agent",
    "load_probe_set",
    "run_probes",
    "script_coverage",
]
