"""Simple SQLite-backed background job queue."""

from __future__ import annotations

import json
import sqlite3
import threading
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from core.db import connect
from core.scope import normalize_user_id


def _connect() -> sqlite3.Connection:
    conn = connect()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS background_jobs (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            job_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            params_json TEXT,
            result_json TEXT,
            error TEXT,
            created_at TEXT NOT NULL,
            completed_at TEXT
        )
        """
    )
    conn.commit()
    return conn


def create_job(user_id: str, job_type: str, params: dict | None = None) -> str:
    job_id = uuid.uuid4().hex
    conn = _connect()
    conn.execute(
        """
        INSERT INTO background_jobs (id, user_id, job_type, status, params_json, created_at)
        VALUES (?, ?, ?, 'pending', ?, ?)
        """,
        (
            job_id,
            normalize_user_id(user_id),
            job_type,
            json.dumps(params or {}),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return job_id


def get_job(job_id: str, user_id: str) -> dict | None:
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM background_jobs WHERE id = ? AND user_id = ?",
        (job_id, normalize_user_id(user_id)),
    ).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    if d.get("result_json"):
        try:
            d["result"] = json.loads(d["result_json"])
        except json.JSONDecodeError:
            d["result"] = None
    return d


def _complete(job_id: str, *, result: Any = None, error: str | None = None) -> None:
    conn = _connect()
    conn.execute(
        """
        UPDATE background_jobs
        SET status = ?, result_json = ?, error = ?, completed_at = ?
        WHERE id = ?
        """,
        (
            "failed" if error else "completed",
            json.dumps(result, default=str) if result is not None else None,
            error,
            datetime.now(timezone.utc).isoformat(),
            job_id,
        ),
    )
    conn.commit()
    conn.close()


def run_in_background(job_id: str, fn: Callable[[], Any]) -> None:
    def _worker():
        try:
            result = fn()
            _complete(job_id, result=result)
        except Exception as exc:
            _complete(job_id, error=f"{exc}\n{traceback.format_exc()}")

    threading.Thread(target=_worker, daemon=True).start()
