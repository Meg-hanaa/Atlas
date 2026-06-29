"""Skill assessment routes (strong model grading only)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.deps import resolve_subject
from assessments.skill_test import generate_assessment, grade_assessment
from auth.deps import CurrentUser, user_id_from
from memory.cross_subject import categories_with_concepts

router = APIRouter(prefix="/assessments", tags=["assessments"])


class GenerateAssessmentRequest(BaseModel):
    category: str
    num_questions: int = Field(default=7, ge=5, le=10)


class GradeAssessmentRequest(BaseModel):
    assessment: dict
    answers: dict[str, str]


@router.get("/{subject}/categories")
def list_categories(subject: str, user: CurrentUser):
    subj = resolve_subject(subject)
    return {"categories": sorted(categories_with_concepts(user_id_from(user), subj).keys())}


@router.post("/{subject}/generate")
def create_assessment(subject: str, body: GenerateAssessmentRequest, user: CurrentUser):
    subj = resolve_subject(subject)
    uid = user_id_from(user)
    try:
        return generate_assessment(uid, subj, body.category, body.num_questions)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{subject}/grade")
def submit_assessment(subject: str, body: GradeAssessmentRequest, user: CurrentUser):
    subj = resolve_subject(subject)
    return grade_assessment(user_id_from(user), subj, body.assessment, body.answers)
