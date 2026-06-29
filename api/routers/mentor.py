"""Mentor nudge routes."""

from __future__ import annotations

from fastapi import APIRouter, Header

from api.deps import resolve_subject
from api.schemas import MentorAckRequest
from auth.deps import CurrentUser, user_id_from
from mentor.state import acknowledge_category, build_mentor_nudges

router = APIRouter(prefix="/mentor", tags=["mentor"])


@router.get("/nudges")
def mentor_nudges(
    user: CurrentUser,
    subject: str | None = None,
    x_session_id: str | None = Header(None, alias="X-Session-Id"),
):
    subj = resolve_subject(subject)
    return build_mentor_nudges(user_id_from(user), subj, session_id=x_session_id)


@router.post("/nudges/acknowledge")
def mentor_acknowledge(body: MentorAckRequest, user: CurrentUser, subject: str | None = None):
    acknowledge_category(user_id_from(user), body.category, resolve_subject(subject))
    return {"ok": True}
