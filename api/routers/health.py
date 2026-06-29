"""Health and config routes."""

from __future__ import annotations

from fastapi import APIRouter

from api.deps import resolve_subject
from api.schemas import HealthResponse
from auth.deps import CurrentUser, user_id_from
from config import MissingConfigError, get_subject
from memory.bank import ensure_bank

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(user: CurrentUser, subject: str | None = None):
    subj = resolve_subject(subject)
    uid = user_id_from(user)
    try:
        ensure_bank(uid, subj)
        hindsight_ok = True
    except MissingConfigError:
        hindsight_ok = False
    return HealthResponse(status="ok", subject=subj, hindsight_ok=hindsight_ok)


@router.get("/config")
def config_info(user: CurrentUser):
    return {"default_subject": get_subject(), "user_id": user_id_from(user)}
