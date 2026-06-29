"""User scoping helpers for multi-tenant data isolation."""

from __future__ import annotations

from config import get_subject

# Pre-auth migration default — existing single-user rows only.
LEGACY_USER_ID = "legacy"


def normalize_user_id(user_id: str) -> str:
    return str(user_id)


def bank_id(user_id: str, subject: str | None = None) -> str:
    """Hindsight bank_id: {user_id}-{subject}"""
    return f"{normalize_user_id(user_id)}-{get_subject(subject)}"


def scope_subject(user_id: str, subject: str | None = None) -> tuple[str, str]:
    """Return (user_id, subject) tuple for SQLite queries."""
    return normalize_user_id(user_id), get_subject(subject)
