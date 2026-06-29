"""Concepts, flashcards, quiz, and revision routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.deps import resolve_subject
from api.schemas import (
    FlashcardGenerateRequest,
    QuizSubmitRequest,
    QuizSubmitResponse,
    SeedConceptsResponse,
)
from api.services.study import submit_quiz
from auth.deps import CurrentUser, user_id_from
from flashcards.generator import apply_flashcard_difficulty_signal, generate_flashcard
from memory.bank import extract_concepts_from_notes
from scheduler.scheduler import get_concept, list_concepts, seed_concepts, todays_revision_summary, weak_concepts

router = APIRouter(tags=["concepts"])


@router.get("/concepts")
def concepts_list(user: CurrentUser, subject: str | None = None):
    return list_concepts(user_id_from(user), resolve_subject(subject))


@router.get("/concepts/weak")
def concepts_weak(user: CurrentUser, subject: str | None = None, threshold: float = 0.6):
    return weak_concepts(user_id_from(user), resolve_subject(subject), threshold=threshold)


@router.get("/concepts/{concept_id}")
def concept_detail(concept_id: int, user: CurrentUser):
    concept = get_concept(concept_id, user_id_from(user))
    if not concept:
        raise HTTPException(status_code=404, detail="Concept not found")
    return concept


@router.get("/revision/today")
def revision_today(user: CurrentUser, subject: str | None = None):
    return todays_revision_summary(user_id_from(user), resolve_subject(subject))


@router.post("/concepts/seed", response_model=SeedConceptsResponse)
def concepts_seed(user: CurrentUser, subject: str | None = None):
    subj = resolve_subject(subject)
    uid = user_id_from(user)
    extracted = extract_concepts_from_notes(uid, subj)
    n = seed_concepts(extracted, uid, subj)
    return SeedConceptsResponse(seeded=n)


@router.post("/concepts/seed-demo-reviews")
def concepts_seed_demo(user: CurrentUser, subject: str | None = None):
    from seed_demo_data import seed_demo_reviews

    return seed_demo_reviews(user_id_from(user), resolve_subject(subject))


@router.post("/flashcards/{subject}/generate")
def flashcard_generate(subject: str, body: FlashcardGenerateRequest, user: CurrentUser):
    subj = resolve_subject(subject)
    uid = user_id_from(user)
    concept = get_concept(body.concept_id, uid)
    if not concept:
        raise HTTPException(status_code=404, detail="Concept not found")
    card = generate_flashcard(concept["name"], concept["category"], uid, subj)
    apply_flashcard_difficulty_signal(concept["id"], uid, card)
    return card


@router.post("/quiz/answer", response_model=QuizSubmitResponse)
def quiz_answer(body: QuizSubmitRequest, user: CurrentUser, subject: str | None = None):
    subj = resolve_subject(subject)
    try:
        result = submit_quiz(
            user_id=user_id_from(user),
            concept_id=body.concept_id,
            question=body.question,
            expected_answer=body.expected_answer,
            user_answer=body.user_answer,
            knew_well=body.knew_well,
            subject=subj,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return QuizSubmitResponse(**result)
