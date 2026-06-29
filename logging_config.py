"""Structured logging setup for Atlas."""

from __future__ import annotations

import logging
import os
import sys


class _StructuredFormatter(logging.Formatter):
    """Key=value log lines for grep-friendly traceability."""

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extras = []
        for key in (
            "video_id",
            "url",
            "ingest",
            "source",
            "subject",
            "confidence",
            "dedup",
            "similarity",
            "path",
        ):
            if hasattr(record, key):
                extras.append(f"{key}={getattr(record, key)}")
        if extras:
            return f"{base} | {' '.join(extras)}"
        return base


def setup_logging(level: str | None = None) -> None:
    log_level = getattr(logging, (level or os.getenv("ATLAS_LOG_LEVEL", "INFO")).upper(), logging.INFO)
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        _StructuredFormatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )
    root.addHandler(handler)
    root.setLevel(log_level)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
