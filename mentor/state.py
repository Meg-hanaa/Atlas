"""Mentor state: per-category timestamps and compounding nudge history."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from core.db import connect, migrate_mentor_tables
from core.scope import normalize_user_id, scope_subject
from memory.bank import reflect_query
from scheduler.scheduler import category_last_touched

STALE_DAYS = 14


def _connect() -> sqlite3.Connection:
    conn = connect()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mentor_category_state (
            user_id TEXT NOT NULL DEFAULT 'legacy',
            subject TEXT NOT NULL,
            category TEXT NOT NULL,
            last_reviewed_at TEXT,
            last_nudge_shown_at TEXT,
            consecutive_ignored_sessions INTEGER NOT NULL DEFAULT 0,
            last_mistake_snippet TEXT,
            PRIMARY KEY (user_id, subject, category)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mentor_nudge_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL DEFAULT 'legacy',
            subject TEXT NOT NULL,
            category TEXT NOT NULL,
            message TEXT NOT NULL,
            mistake_snippet TEXT,
            shown_at TEXT NOT NULL,
            acknowledged_at TEXT,
            session_id TEXT
        )
        """
    )
    migrate_mentor_tables(conn)
    conn.commit()
    return conn


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_state(conn: sqlite3.Connection, user_id: str, subject: str, category: str) -> sqlite3.Row | None:
    uid = normalize_user_id(user_id)
    return conn.execute(
        "SELECT * FROM mentor_category_state WHERE user_id = ? AND subject = ? AND category = ?",
        (uid, subject, category),
    ).fetchone()


def record_category_activity(user_id: str, category: str, subject: str | None = None) -> None:
    uid, subj = scope_subject(user_id, subject)
    now = _now_iso()
    conn = _connect()
    conn.execute(
        """
        INSERT INTO mentor_category_state (user_id, subject, category, last_reviewed_at, consecutive_ignored_sessions)
        VALUES (?, ?, ?, ?, 0)
        ON CONFLICT(user_id, subject, category) DO UPDATE SET
            last_reviewed_at = excluded.last_reviewed_at,
            consecutive_ignored_sessions = 0
        """,
        (uid, subj, category, now),
    )
    conn.execute(
        """
        UPDATE mentor_nudge_history
        SET acknowledged_at = ?
        WHERE user_id = ? AND subject = ? AND category = ? AND acknowledged_at IS NULL
        """,
        (now, uid, subj, category),
    )
    conn.commit()
    conn.close()


def acknowledge_category(user_id: str, category: str, subject: str | None = None) -> None:
    uid, subj = scope_subject(user_id, subject)
    now = _now_iso()
    conn = _connect()
    conn.execute(
        """
        UPDATE mentor_nudge_history
        SET acknowledged_at = ?
        WHERE user_id = ? AND subject = ? AND category = ? AND acknowledged_at IS NULL
        """,
        (now, uid, subj, category),
    )
    conn.commit()
    conn.close()


def _fetch_mistake_snippet(user_id: str, category: str, subject: str) -> str:
    try:
        text = reflect_query(
            user_id,
            f"What is the most common mistake pattern in '{category}' based on my study notes?",
            subject=subject,
            budget="low",
        )
        return text[:400]
    except Exception:
        return ""


def build_mentor_nudges(user_id: str, subject: str | None = None, session_id: str | None = None) -> list[dict]:
    uid, subj = scope_subject(user_id, subject)
    session = session_id or _now_iso()[:10]
    cat_touch = category_last_touched(uid, subj)
    stale = [cat for cat, days in cat_touch.items() if days is not None and days >= STALE_DAYS]
    if not stale:
        return []

    conn = _connect()
    nudges: list[dict] = []
    try:
        for category in sorted(stale):
            state = _get_state(conn, uid, subj, category)
            days_stale = int(cat_touch[category] or STALE_DAYS)

            already_this_session = conn.execute(
                """
                SELECT message, mistake_snippet FROM mentor_nudge_history
                WHERE user_id = ? AND subject = ? AND category = ? AND session_id = ?
                LIMIT 1
                """,
                (uid, subj, category, session),
            ).fetchone()

            if already_this_session:
                state = _get_state(conn, uid, subj, category)
                ignored = int(state["consecutive_ignored_sessions"] or 0) if state else 0
                nudges.append(
                    {
                        "category": category,
                        "days_stale": days_stale,
                        "message": already_this_session["message"],
                        "mistake_snippet": already_this_session["mistake_snippet"] or "",
                        "ignored_sessions": ignored,
                    }
                )
                continue

            ignored = 0
            mistake = ""
            if state:
                last_shown = state["last_nudge_shown_at"]
                if last_shown and not state["last_reviewed_at"]:
                    ignored = int(state["consecutive_ignored_sessions"] or 0) + 1
                elif last_shown and state["last_reviewed_at"]:
                    if state["last_reviewed_at"] < last_shown:
                        ignored = int(state["consecutive_ignored_sessions"] or 0) + 1
                    else:
                        ignored = 0
                mistake = state["last_mistake_snippet"] or ""

            if not mistake:
                mistake = _fetch_mistake_snippet(uid, category, subj)

            if ignored >= 2:
                prefix = f"You've ignored nudges about **{category}** for **{ignored} sessions** now. "
            elif ignored == 1:
                prefix = f"Still no review in **{category}** since last nudge. "
            else:
                prefix = f"You haven't touched **{category}** in **{days_stale}+ days**. "

            body = mistake[:220] + ("…" if len(mistake) > 220 else "") if mistake else "Time to review!"
            message = prefix + body

            now = _now_iso()
            conn.execute(
                """
                INSERT INTO mentor_category_state
                    (user_id, subject, category, last_nudge_shown_at, consecutive_ignored_sessions, last_mistake_snippet)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, subject, category) DO UPDATE SET
                    last_nudge_shown_at = excluded.last_nudge_shown_at,
                    consecutive_ignored_sessions = excluded.consecutive_ignored_sessions,
                    last_mistake_snippet = excluded.last_mistake_snippet
                """,
                (uid, subj, category, now, ignored, mistake),
            )
            conn.execute(
                """
                INSERT INTO mentor_nudge_history
                    (user_id, subject, category, message, mistake_snippet, shown_at, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (uid, subj, category, message, mistake, now, session),
            )
            nudges.append(
                {
                    "category": category,
                    "days_stale": days_stale,
                    "message": message,
                    "mistake_snippet": mistake,
                    "ignored_sessions": ignored,
                }
            )
        conn.commit()
    finally:
        conn.close()

    return nudges
