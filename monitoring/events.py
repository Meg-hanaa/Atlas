"""Local structured event log for Atlas operations (no external service)."""

from __future__ import annotations

import json
import logging
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

logger = logging.getLogger(__name__)

EVENTS_LOG = Path(__file__).resolve().parent.parent / "data" / "atlas_events.jsonl"


def _write_event(record: dict) -> None:
    EVENTS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with EVENTS_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


def record_event(
    operation: str,
    attributes: dict[str, Any] | None = None,
    *,
    duration_ms: float | None = None,
    error: bool = False,
    error_message: str | None = None,
) -> None:
    """Append one structured operation event to data/atlas_events.jsonl."""
    attrs = attributes or {}
    row = {
        "operation": operation,
        "subject": attrs.get("subject") or os.getenv("ATLAS_SUBJECT", "ml-notes"),
        "status": "error" if error else "ok",
        "duration_ms": duration_ms,
        "model_used": attrs.get("model_used"),
        "total_cost": attrs.get("total_cost"),
        "cascaded": attrs.get("cascaded"),
        "recall_hit_count": attrs.get("recall_hit_count"),
        "grounded": attrs.get("grounded"),
        "ocr_confidence": attrs.get("ocr_confidence"),
        "transcription_method": attrs.get("transcription_method"),
        "source": attrs.get("source"),
        "error_message": error_message,
        "attributes_json": json.dumps(attrs, default=str)[:8000],
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_event(row)


class _SpanProxy:
    def __init__(self):
        self._attrs: dict[str, Any] = {}

    def set_attribute(self, key: str, value: Any) -> None:
        self._attrs[key] = value


@contextmanager
def trace_span(
    name: str,
    attributes: dict[str, Any] | None = None,
    kind: str = "internal",
) -> Iterator[_SpanProxy]:
    del kind
    proxy = _SpanProxy()
    merged = dict(attributes or {})
    start = time.perf_counter()
    err: Exception | None = None
    try:
        yield proxy
        merged.update(proxy._attrs)
    except Exception as exc:
        err = exc
        merged.update(proxy._attrs)
        raise
    finally:
        record_event(
            name,
            merged,
            duration_ms=(time.perf_counter() - start) * 1000,
            error=err is not None,
            error_message=str(err) if err else None,
        )


def set_span_attributes(span: Any, **attrs: Any) -> None:
    if span is None:
        return
    for key, value in attrs.items():
        if value is not None:
            span.set_attribute(key, value)


def flush_traces() -> None:
    """No-op — events are written synchronously."""
