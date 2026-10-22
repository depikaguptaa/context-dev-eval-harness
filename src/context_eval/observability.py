"""Per-call observability: every API call is logged as one JSONL record.

Recorded per call: timestamp, operation, target (URL or query), latency,
HTTP status, credits consumed (from key_metadata.credits_consumed when the
API reports it), and a free-form notes field. This is the piece that maps
to production LLM observability work: cost and quality per step, not just
per request.
"""

from __future__ import annotations

import json
import time
from pathlib import Path


class Observer:
    def __init__(self, log_path: str | Path | None = None):
        self.log_path = Path(log_path) if log_path else None
        self.records: list[dict] = []

    def record(
        self,
        operation: str,
        target: str,
        latency_ms: float,
        status: int | None,
        credits: int | None = None,
        ok: bool = True,
        notes: str = "",
    ) -> dict:
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "operation": operation,
            "target": target,
            "latency_ms": round(latency_ms, 1),
            "status": status,
            "credits": credits,
            "ok": ok,
            "notes": notes,
        }
        self.records.append(record)
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

    def summarize(self) -> dict:
        total = len(self.records)
        ok = sum(1 for r in self.records if r["ok"])
        credits = sum(r["credits"] for r in self.records if r["credits"])
        latency = [r["latency_ms"] for r in self.records]
        by_op: dict[str, int] = {}
        for r in self.records:
            by_op[r["operation"]] = by_op.get(r["operation"], 0) + 1
        return {
            "calls": total,
            "ok": ok,
            "failed": total - ok,
            "credits_charged": credits,
            "avg_latency_ms": round(sum(latency) / len(latency), 1) if latency else 0,
            "by_operation": by_op,
        }
