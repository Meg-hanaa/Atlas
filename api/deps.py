"""FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Header, Query

from auth.deps import CurrentUser, user_id_from
from config import get_subject

SubjectDep = Annotated[str, Query(alias="subject")]


def resolve_subject(subject: str | None = Query(None, description="Subject slug, e.g. ml-notes")) -> str:
    return get_subject(subject)


def resolve_user_id(user: CurrentUser) -> str:
    return user_id_from(user)


UserIdDep = Annotated[str, Query()]  # placeholder type hint only


def get_user_id(user: CurrentUser) -> str:
    return user_id_from(user)
