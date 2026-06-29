"""Ingest text from PDF files via pdfplumber."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import pdfplumber
from monitoring.tracing import trace_span

logger = logging.getLogger(__name__)


def ingest_pdf(path: str, subject: str) -> dict:
    """
    Extract text from a PDF file.

    Returns: {"subject", "source", "content", "date"}
    """
    if not os.path.isfile(path):
        logger.error("PDF not found", extra={"path": path, "ingest": "pdf"})
        raise FileNotFoundError(f"PDF not found: {path}")

    with trace_span("ingest.pdf", {"path": path, "subject": subject}):
        pages: list[str] = []
        try:
            with pdfplumber.open(path) as pdf:
                for i, page in enumerate(pdf.pages):
                    try:
                        text = page.extract_text() or ""
                    except Exception as exc:
                        logger.warning(
                            "Failed to extract PDF page %s: %s",
                            i,
                            exc,
                            extra={"path": path, "page": i, "ingest": "pdf"},
                        )
                        continue
                    if text.strip():
                        pages.append(text)
        except Exception as exc:
            logger.error(
                "Malformed or unreadable PDF: %s",
                exc,
                extra={"path": path, "ingest": "pdf"},
            )
            raise ValueError(f"Could not read PDF: {path}") from exc

    content = "\n\n".join(pages)
    if not content.strip():
        logger.error("No extractable text in PDF", extra={"path": path, "ingest": "pdf"})
        raise ValueError(f"No extractable text in PDF: {path}")

    source = f"pdf:{os.path.basename(path)}"
    return {
        "subject": subject,
        "source": source,
        "content": content,
        "date": datetime.now(timezone.utc).isoformat(),
    }
