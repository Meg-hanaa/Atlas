"""SQLite spaced-repetition scheduler using FSRS (v6, 21 parameters)."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone

from fsrs import Card, Rating, Scheduler

from config import get_subject
from core.db import connect, migrate_concepts_table
from core.scope import normalize_user_id, scope_subject

logger = logging.getLogger(__name__)

_fsrs = Scheduler()
DUE_THRESHOLD = 0.9


def _connect() -> sqlite3.Connection:
    conn = connect()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS concepts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL DEFAULT 'legacy',
            subject TEXT NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            stability REAL,
            last_reviewed TEXT,
            repetitions INTEGER NOT NULL DEFAULT 0,
            fsrs_card_json TEXT,
            UNIQUE(user_id, subject, name)
        )
        """
    )
    cols = {row[1] for row in conn.execute("PRAGMA table_info(concepts)")}
    if "fsrs_card_json" not in cols:
        conn.execute("ALTER TABLE concepts ADD COLUMN fsrs_card_json TEXT")
    migrate_concepts_table(conn)
    conn.commit()
    return conn


def _card_from_row(row: sqlite3.Row) -> Card:
    raw = row["fsrs_card_json"]
    if raw:
        try:
            return Card.from_dict(json.loads(raw))
        except Exception as exc:
            logger.warning("Invalid fsrs_card_json for concept %s: %s", row["id"], exc)
    return Card()


def _persist_card(conn: sqlite3.Connection, concept_id: int, card: Card, repetitions: int) -> None:
    last = card.last_review.isoformat() if card.last_review else None
    conn.execute(
        """
        UPDATE concepts
        SET fsrs_card_json = ?, stability = ?, last_reviewed = ?, repetitions = ?
        WHERE id = ?
        """,
        (
            json.dumps(card.to_dict(), default=str),
            float(card.stability or 0),
            last,
            repetitions,
            concept_id,
        ),
    )


def recall_strength(card: Card, now: datetime | None = None) -> float:
    return _fsrs.get_card_retrievability(card, current_datetime=now)


def grade_to_rating(*, correct: bool, partial: bool = False, easy: bool = False) -> Rating:
    if not correct and not partial:
        return Rating.Again
    if partial:
        return Rating.Hard
    if easy:
        return Rating.Easy
    return Rating.Good


def _get_row(conn: sqlite3.Connection, concept_id: int, user_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM concepts WHERE id = ? AND user_id = ?",
        (concept_id, normalize_user_id(user_id)),
    ).fetchone()


def update_after_review(
    concept_id: int,
    user_id: str,
    correct: bool,
    partial: bool = False,
    easy: bool = False,
    review_datetime: datetime | None = None,
) -> None:
    conn = _connect()
    row = _get_row(conn, concept_id, user_id)
    if not row:
        conn.close()
        return

    card = _card_from_row(row)
    rating = grade_to_rating(correct=correct, partial=partial, easy=easy)
    card, review_log = _fsrs.review_card(card, rating, review_datetime=review_datetime)
    r_after = recall_strength(card, review_datetime)

    repetitions = int(row["repetitions"])
    if rating in (Rating.Good, Rating.Easy):
        repetitions += 1
    elif rating == Rating.Again:
        repetitions = max(0, repetitions - 1)

    _persist_card(conn, concept_id, card, repetitions)
    conn.commit()
    conn.close()

    from analytics.review_log import persist_review_log

    persist_review_log(
        user_id=user_id,
        subject=row["subject"],
        concept_id=concept_id,
        concept_name=row["name"],
        review_log=review_log,
        retrievability=r_after,
        stability=float(card.stability or 0),
        difficulty=float(card.difficulty or 0),
        review_source="quiz",
    )


def apply_generation_escalation_signal(concept_id: int, user_id: str) -> None:
    conn = _connect()
    row = _get_row(conn, concept_id, user_id)
    if not row:
        conn.close()
        return
    card = _card_from_row(row)
    card, review_log = _fsrs.review_card(card, Rating.Hard)
    repetitions = int(row["repetitions"])
    _persist_card(conn, concept_id, card, repetitions)
    conn.commit()
    conn.close()

    from analytics.review_log import persist_review_log

    persist_review_log(
        user_id=user_id,
        subject=row["subject"],
        concept_id=concept_id,
        concept_name=row["name"],
        review_log=review_log,
        retrievability=recall_strength(card),
        stability=float(card.stability or 0),
        difficulty=float(card.difficulty or 0),
        review_source="generation_escalation",
    )


def seed_concepts(concepts: list[dict], user_id: str, subject: str | None = None) -> int:
    uid, subj = scope_subject(user_id, subject)
    conn = _connect()
    added = 0
    for c in concepts:
        name = c.get("name", "").strip()
        category = c.get("category", "General").strip()
        if not name:
            continue
        card = Card()
        try:
            conn.execute(
                """
                INSERT INTO concepts
                    (user_id, subject, name, category, stability, last_reviewed, repetitions, fsrs_card_json)
                VALUES (?, ?, ?, ?, ?, NULL, 0, ?)
                """,
                (uid, subj, name, category, 0.0, json.dumps(card.to_dict(), default=str)),
            )
            added += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()
    return added


def _concept_dict(row: sqlite3.Row, now: datetime | None = None) -> dict:
    card = _card_from_row(row)
    r = recall_strength(card, now=now)
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "subject": row["subject"],
        "name": row["name"],
        "category": row["category"],
        "stability": float(card.stability or row["stability"] or 0),
        "difficulty": float(card.difficulty or 0),
        "last_reviewed": row["last_reviewed"],
        "repetitions": row["repetitions"],
        "recall_strength": r,
        "fsrs_due": card.due.isoformat() if card.due else None,
    }


def list_concepts(user_id: str, subject: str | None = None) -> list[dict]:
    uid, subj = scope_subject(user_id, subject)
    now = datetime.now(timezone.utc)
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM concepts WHERE user_id = ? AND subject = ? ORDER BY category, name",
        (uid, subj),
    ).fetchall()
    conn.close()
    return [_concept_dict(row, now) for row in rows]


def get_concept(concept_id: int, user_id: str) -> dict | None:
    conn = _connect()
    row = _get_row(conn, concept_id, user_id)
    conn.close()
    if not row:
        return None
    return _concept_dict(row)


def due_concepts(user_id: str, subject: str | None = None, threshold: float | None = None) -> list[dict]:
    thresh = threshold if threshold is not None else (1.0 - _fsrs.desired_retention + 0.1)
    return [c for c in list_concepts(user_id, subject) if c["recall_strength"] < thresh]


def weak_concepts(user_id: str, subject: str | None = None, threshold: float = 0.6) -> list[dict]:
    return due_concepts(user_id, subject, threshold)


def apply_synthetic_review(
    concept_id: int,
    user_id: str,
    rating: Rating,
    review_datetime: datetime,
) -> None:
    conn = _connect()
    row = _get_row(conn, concept_id, user_id)
    if not row:
        conn.close()
        return
    card = _card_from_row(row)
    card, review_log = _fsrs.review_card(card, rating, review_datetime=review_datetime)
    reps = int(row["repetitions"]) + (1 if rating in (Rating.Good, Rating.Easy) else 0)
    _persist_card(conn, concept_id, card, reps)
    conn.commit()
    conn.close()

    from analytics.review_log import persist_review_log

    persist_review_log(
        user_id=user_id,
        subject=row["subject"],
        concept_id=concept_id,
        concept_name=row["name"],
        review_log=review_log,
        retrievability=recall_strength(card, review_datetime),
        stability=float(card.stability or 0),
        difficulty=float(card.difficulty or 0),
        review_source="synthetic",
    )


def set_last_reviewed(concept_id: int, user_id: str, iso_date: str) -> None:
    dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
    apply_synthetic_review(concept_id, user_id, Rating.Good, dt)


def category_last_touched(user_id: str, subject: str | None = None) -> dict[str, float | None]:
    now = datetime.now(timezone.utc)
    by_cat: dict[str, list[float]] = {}
    for c in list_concepts(user_id, subject):
        cat = c["category"]
        if c["last_reviewed"]:
            reviewed = datetime.fromisoformat(c["last_reviewed"].replace("Z", "+00:00"))
            days = (now - reviewed).total_seconds() / 86400.0
            by_cat.setdefault(cat, []).append(days)
        else:
            by_cat.setdefault(cat, []).append(999.0)
    return {cat: min(days) if days else None for cat, days in by_cat.items()}


def todays_revision_summary(user_id: str, subject: str | None = None) -> dict:
    due = due_concepts(user_id, subject)
    mins = max(1, len(due) * 2)
    if not due:
        difficulty = "light"
    elif len(due) > 10:
        difficulty = "heavy"
    else:
        difficulty = "moderate"
    return {
        "due_count": len(due),
        "estimate_minutes": mins,
        "difficulty": difficulty,
    }
