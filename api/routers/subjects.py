"""Subject (book) registry routes."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from auth.deps import CurrentUser, user_id_from
from core.subjects import add_subject, list_subjects, slugify_subject
from memory.bank import ensure_bank

router = APIRouter(prefix="/subjects", tags=["subjects"])


class CreateSubjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)


@router.get("")
def get_subjects(user: CurrentUser):
    uid = user_id_from(user)
    subjects = list_subjects(uid)
    if not subjects:
        from config import DEFAULT_SUBJECT

        default = add_subject(uid, DEFAULT_SUBJECT)
        ensure_bank(uid, default["slug"])
        subjects = [default]
    return {"subjects": subjects}


@router.post("")
def create_subject(body: CreateSubjectRequest, user: CurrentUser):
    uid = user_id_from(user)
    subject = add_subject(uid, body.name)
    ensure_bank(uid, subject["slug"])
    return subject


@router.get("/{slug}/validate")
def validate_slug(slug: str, user: CurrentUser):
    return {"slug": slugify_subject(slug)}
