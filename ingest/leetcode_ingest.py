"""Ingest pasted LeetCode question prompts."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib


def ingest_leetcode(prompt_text: str, subject: str, title: str | None = None) -> dict:
    """
    Normalize a pasted LeetCode problem into a chunk.

    Returns: {"subject", "source", "content", "date"}
    """
    content = prompt_text.strip()
    if not content:
        raise ValueError("LeetCode prompt text is empty")

    if title:
        label = title.strip().replace(" ", "-").lower()
    else:
        digest = hashlib.sha256(content.encode()).hexdigest()[:8]
        label = f"problem-{digest}"

    source = f"leetcode:{label}"
    return {
        "subject": subject,
        "source": source,
        "content": content,
        "date": datetime.now(timezone.utc).isoformat(),
    }
