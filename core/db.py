"""Shared SQLite helpers and user_id migrations."""

from __future__ import annotations

import os
import sqlite3

from config import DB_PATH


def connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    return column in cols


def migrate_add_user_id(conn: sqlite3.Connection, table: str, default: str = "legacy") -> None:
    if not _has_column(conn, table, "user_id"):
        conn.execute(
            f"ALTER TABLE {table} ADD COLUMN user_id TEXT NOT NULL DEFAULT '{default}'"
        )


def migrate_concepts_table(conn: sqlite3.Connection) -> None:
    """Rebuild concepts with UNIQUE(user_id, subject, name) if needed."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='concepts'"
    ).fetchone()
    if not row:
        return
    ddl = row[0] or ""
    if "UNIQUE(user_id, subject, name)" in ddl.replace("\n", " "):
        return

    migrate_add_user_id(conn, "concepts")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS concepts_v2 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
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
    conn.execute(
        """
        INSERT OR IGNORE INTO concepts_v2
            (id, user_id, subject, name, category, stability, last_reviewed, repetitions, fsrs_card_json)
        SELECT id, user_id, subject, name, category, stability, last_reviewed, repetitions, fsrs_card_json
        FROM concepts
        """
    )
    conn.execute("DROP TABLE concepts")
    conn.execute("ALTER TABLE concepts_v2 RENAME TO concepts")


def migrate_mentor_tables(conn: sqlite3.Connection) -> None:
    migrate_add_user_id(conn, "mentor_category_state")
    migrate_add_user_id(conn, "mentor_nudge_history")
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='mentor_category_state'"
    ).fetchone()
    if not row:
        return
    ddl = row[0] or ""
    if "PRIMARY KEY (user_id, subject, category)" in ddl.replace("\n", " "):
        return

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mentor_category_state_v2 (
            user_id TEXT NOT NULL,
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
        INSERT OR REPLACE INTO mentor_category_state_v2
        SELECT user_id, subject, category, last_reviewed_at, last_nudge_shown_at,
               consecutive_ignored_sessions, last_mistake_snippet
        FROM mentor_category_state
        """
    )
    conn.execute("DROP TABLE mentor_category_state")
    conn.execute("ALTER TABLE mentor_category_state_v2 RENAME TO mentor_category_state")

    migrate_add_user_id(conn, "mentor_nudge_history")
