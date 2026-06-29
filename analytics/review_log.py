"""Persist FSRS ReviewLog entries and query review history."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from core.db import connect
from core.scope import normalize_user_id, scope_subject


def _connect() -> sqlite3.Connection:
    conn = connect()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS fsrs_review_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            subject TEXT NOT NULL,
            concept_id INTEGER NOT NULL,
            concept_name TEXT NOT NULL,
            rating INTEGER NOT NULL,
            retrievability REAL,
            stability REAL,
            difficulty REAL,
            review_datetime TEXT NOT NULL,
            review_source TEXT NOT NULL DEFAULT 'quiz',
            log_json TEXT
        )
        """
    )
    conn.commit()
    return conn


def persist_review_log(
    *,
    user_id: str,
    subject: str,
    concept_id: int,
    concept_name: str,
    review_log,
    retrievability: float | None = None,
    stability: float | None = None,
    difficulty: float | None = None,
    review_source: str = "quiz",
) -> None:
    uid, subj = scope_subject(user_id, subject)
    log_dict = review_log.to_dict() if hasattr(review_log, "to_dict") else dict(review_log)
    reviewed_at = log_dict.get("review_datetime") or datetime.now(timezone.utc).isoformat()
    conn = _connect()
    conn.execute(
        """
        INSERT INTO fsrs_review_log
            (user_id, subject, concept_id, concept_name, rating, retrievability,
             stability, difficulty, review_datetime, review_source, log_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            uid,
            subj,
            concept_id,
            concept_name,
            int(log_dict.get("rating", 0)),
            retrievability,
            stability,
            difficulty,
            reviewed_at,
            review_source,
            json.dumps(log_dict, default=str),
        ),
    )
    conn.commit()
    conn.close()


def review_history(
    user_id: str,
    subject: str | None = None,
    concept_id: int | None = None,
    limit: int = 500,
) -> list[dict]:
    uid, subj = scope_subject(user_id, subject)
    conn = _connect()
    if concept_id is not None:
        rows = conn.execute(
            """
            SELECT * FROM fsrs_review_log
            WHERE user_id = ? AND subject = ? AND concept_id = ?
            ORDER BY review_datetime ASC
            LIMIT ?
            """,
            (uid, subj, concept_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM fsrs_review_log
            WHERE user_id = ? AND subject = ?
            ORDER BY review_datetime ASC
            LIMIT ?
            """,
            (uid, subj, limit),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def retrievability_timeline(user_id: str, subject: str | None = None) -> list[dict]:
    """Per-concept retrievability snapshots from review log."""
    history = review_history(user_id, subject)
    by_concept: dict[int, list] = {}
    for row in history:
        by_concept.setdefault(row["concept_id"], []).append(
            {
                "concept_id": row["concept_id"],
                "concept_name": row["concept_name"],
                "retrievability": row["retrievability"],
                "review_datetime": row["review_datetime"],
                "rating": row["rating"],
            }
        )
    return [{"concept_id": cid, "points": pts} for cid, pts in by_concept.items()]
