"""Deduplicate and merge near-identical chunks before Hindsight retain."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone

from config import get_subject
from core.db import connect, migrate_add_user_id
from core.scope import scope_subject

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.60


def _connect() -> sqlite3.Connection:
    conn = connect()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chunk_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL DEFAULT 'legacy',
            subject TEXT NOT NULL,
            sources TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    migrate_add_user_id(conn, "chunk_index")
    conn.commit()
    return conn


def _similarity_matrix(texts: list[str]):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    if len(texts) == 1:
        return [[1.0]]
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        max_features=8000,
    )
    matrix = vectorizer.fit_transform(texts)
    return cosine_similarity(matrix).tolist()


def _best_similarity(new_text: str, existing_text: str) -> float:
    import difflib

    tfidf_sim = _similarity_matrix([new_text, existing_text])[0][1]
    seq_sim = difflib.SequenceMatcher(
        None, new_text.lower(), existing_text.lower()
    ).ratio()
    words_a = set(new_text.lower().split())
    words_b = set(existing_text.lower().split())
    union = words_a | words_b
    jaccard = (len(words_a & words_b) / len(union)) if union else 0.0
    return max(tfidf_sim, seq_sim, jaccard)


def list_indexed(user_id: str, subject: str | None = None) -> list[dict]:
    uid, subj = scope_subject(user_id, subject)
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM chunk_index WHERE user_id = ? AND subject = ? ORDER BY id",
        (uid, subj),
    ).fetchall()
    conn.close()
    result = []
    for row in rows:
        result.append(
            {
                "id": row["id"],
                "subject": row["subject"],
                "sources": json.loads(row["sources"]),
                "content": row["content"],
                "created_at": row["created_at"],
            }
        )
    return result


def _insert_index(user_id: str, subject: str, sources: list[str], content: str) -> int:
    uid, subj = scope_subject(user_id, subject)
    conn = _connect()
    cur = conn.execute(
        """
        INSERT INTO chunk_index (user_id, subject, sources, content, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (uid, subj, json.dumps(sources), content, datetime.now(timezone.utc).isoformat()),
    )
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


def _update_index(index_id: int, sources: list[str]) -> None:
    conn = _connect()
    conn.execute(
        "UPDATE chunk_index SET sources = ? WHERE id = ?",
        (json.dumps(sources), index_id),
    )
    conn.commit()
    conn.close()


def prepare_chunk_for_retain(chunk: dict, user_id: str) -> tuple[dict | None, str]:
    """
    Dedup pass before retain.

    Returns (chunk_to_retain, action) where action is:
      - "retain" — new unique chunk
      - "merge" — merged with existing (retain consolidated attribution)
      - "skip" — near-duplicate, sources merged in index only
    """
    subject = get_subject(chunk.get("subject"))
    source = chunk["source"]
    content = chunk["content"].strip()
    if not content:
        return None, "skip"

    indexed = list_indexed(user_id, subject)
    for entry in indexed:
        sim = _best_similarity(content, entry["content"])
        if sim >= SIMILARITY_THRESHOLD:
            sources = list(entry["sources"])
            if source not in sources:
                sources.append(source)
                _update_index(entry["id"], sources)
                logger.info(
                    "Merged duplicate chunk: %s into index #%s (sim=%.2f)",
                    source,
                    entry["id"],
                    sim,
                    extra={
                        "subject": subject,
                        "source": source,
                        "similarity": sim,
                        "merged_sources": sources,
                        "dedup": "merge",
                    },
                )
                merged_chunk = {
                    **chunk,
                    "source": ",".join(sources),
                    "content": entry["content"],
                    "merged_sources": sources,
                    "dedup_action": "merge",
                }
                return merged_chunk, "merge"
            logger.info(
                "Skipping duplicate retain for %s (already in index #%s, sim=%.2f)",
                source,
                entry["id"],
                sim,
                extra={"subject": subject, "source": source, "dedup": "skip"},
            )
            return None, "skip"

    _insert_index(user_id, subject, [source], content)
    return {**chunk, "dedup_action": "retain"}, "retain"


def format_retain_context(chunk: dict) -> str:
    """Build context string with merged source attribution."""
    merged = chunk.get("merged_sources")
    if merged:
        return f"sources={','.join(merged)}"
    return f"source={chunk['source']}"
