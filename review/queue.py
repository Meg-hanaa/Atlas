"""Review queue with per-user isolation."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

from core.db import connect, migrate_add_user_id
from core.scope import normalize_user_id, scope_subject

logger = logging.getLogger(__name__)


def _connect() -> sqlite3.Connection:
    conn = connect()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS needs_review (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL DEFAULT 'legacy',
            subject TEXT NOT NULL,
            source TEXT NOT NULL,
            path TEXT NOT NULL,
            transcription TEXT NOT NULL,
            alt_transcription TEXT,
            confidence REAL NOT NULL,
            reason TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL
        )
        """
    )
    migrate_add_user_id(conn, "needs_review")
    conn.commit()
    return conn


def enqueue(
    user_id: str,
    subject: str,
    source: str,
    path: str,
    transcription: str,
    confidence: float,
    reason: str,
    alt_transcription: str | None = None,
) -> int:
    uid, subj = scope_subject(user_id, subject)
    now = datetime.now(timezone.utc).isoformat()
    conn = _connect()
    cur = conn.execute(
        """
        INSERT INTO needs_review
            (user_id, subject, source, path, transcription, alt_transcription, confidence, reason, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
        """,
        (uid, subj, source, path, transcription, alt_transcription, confidence, reason, now),
    )
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    logger.warning(
        "OCR queued for review: %s confidence=%.2f reason=%s",
        source,
        confidence,
        reason,
        extra={"user_id": uid, "subject": subj, "source": source, "confidence": confidence},
    )
    return row_id


def list_pending(user_id: str, subject: str | None = None) -> list[dict]:
    uid, subj = scope_subject(user_id, subject)
    conn = _connect()
    rows = conn.execute(
        """
        SELECT * FROM needs_review
        WHERE status = 'pending' AND user_id = ? AND subject = ?
        ORDER BY created_at DESC
        """,
        (uid, subj),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_item(item_id: int, user_id: str) -> dict | None:
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM needs_review WHERE id = ? AND user_id = ?",
        (item_id, normalize_user_id(user_id)),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def approve(item_id: int, user_id: str, edited_text: str | None = None) -> dict:
    item = get_item(item_id, user_id)
    if not item:
        raise ValueError(f"Review item {item_id} not found")
    text = edited_text if edited_text is not None else item["transcription"]
    conn = _connect()
    conn.execute(
        "UPDATE needs_review SET status = 'approved', transcription = ? WHERE id = ? AND user_id = ?",
        (text, item_id, normalize_user_id(user_id)),
    )
    conn.commit()
    conn.close()
    return {
        "subject": item["subject"],
        "source": item["source"],
        "content": text,
        "date": item["created_at"],
        "ocr_confidence": item["confidence"],
        "reviewed": True,
    }


def reject(item_id: int, user_id: str) -> None:
    conn = _connect()
    conn.execute(
        "UPDATE needs_review SET status = 'rejected' WHERE id = ? AND user_id = ?",
        (item_id, normalize_user_id(user_id)),
    )
    conn.commit()
    conn.close()
