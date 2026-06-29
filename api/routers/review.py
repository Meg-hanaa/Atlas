"""OCR review queue routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.deps import resolve_subject
from api.schemas import ReviewApproveRequest
from auth.deps import CurrentUser, user_id_from
from memory.bank import retain_ingested
from review.queue import approve, list_pending, reject

router = APIRouter(prefix="/review-queue", tags=["review"])


@router.get("")
def review_list(user: CurrentUser, subject: str | None = None):
    return list_pending(user_id_from(user), resolve_subject(subject))


@router.post("/{item_id}/approve")
def review_approve(item_id: int, body: ReviewApproveRequest, user: CurrentUser, subject: str | None = None):
    uid = user_id_from(user)
    try:
        chunk = approve(item_id, uid, body.edited_text)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    retain_ingested(uid, chunk)
    return {"ok": True, "source": chunk["source"], "subject": resolve_subject(subject)}


@router.post("/{item_id}/reject")
def review_reject(item_id: int, user: CurrentUser):
    reject(item_id, user_id_from(user))
    return {"ok": True}
