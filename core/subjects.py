"""Per-user subject registry (separate Hindsight banks / SQLite namespaces)."""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone

from core.db import connect
from core.scope import normalize_user_id

_TABLE = """
CREATE TABLE IF NOT EXISTS user_subjects (
    user_id TEXT NOT NULL,
    slug TEXT NOT NULL,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, slug)
)
"""


def slugify_subject(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s).strip("-")
    return s or "notes"


def _connect() -> sqlite3.Connection:
    conn = connect()
    conn.execute(_TABLE)
    conn.commit()
    return conn


def list_subjects(user_id: str) -> list[dict]:
    uid = normalize_user_id(user_id)
    conn = _connect()
    rows = conn.execute(
        "SELECT slug, display_name, created_at FROM user_subjects WHERE user_id = ? ORDER BY created_at ASC",
        (uid,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_subject(user_id: str, name: str) -> dict:
    uid = normalize_user_id(user_id)
    slug = slugify_subject(name)
    display = name.strip() or slug
    created = datetime.now(timezone.utc).isoformat()
    conn = _connect()
    conn.execute(
        """
        INSERT INTO user_subjects (user_id, slug, display_name, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, slug) DO UPDATE SET display_name = excluded.display_name
        """,
        (uid, slug, display, created),
    )
    conn.commit()
    conn.close()
    return {"slug": slug, "display_name": display, "created_at": created}


def ensure_subject(user_id: str, slug: str, display_name: str | None = None) -> dict:
    """Register subject if missing (e.g. first ingest)."""
    uid = normalize_user_id(user_id)
    normalized = slugify_subject(slug)
    existing = list_subjects(uid)
    if any(s["slug"] == normalized for s in existing):
        return next(s for s in existing if s["slug"] == normalized)
    return add_subject(uid, display_name or normalized)
