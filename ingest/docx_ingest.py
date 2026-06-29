"""Extract text from Word .docx uploads."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from monitoring.tracing import trace_span


def ingest_docx(path: str, subject: str) -> dict:
    from docx import Document

    if not os.path.isfile(path):
        raise FileNotFoundError(f"Document not found: {path}")

    with trace_span("ingest.docx", {"path": path, "subject": subject}):
        doc = Document(path)
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        content = "\n\n".join(paragraphs)

    if not content.strip():
        raise ValueError("No text found in document")

    basename = os.path.basename(path)
    source = f"docx:{basename}"
    return {
        "subject": subject,
        "source": source,
        "content": content,
        "date": datetime.now(timezone.utc).isoformat(),
    }
