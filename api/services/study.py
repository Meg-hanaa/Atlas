"""Quiz and interview submission orchestration."""

from __future__ import annotations

from flashcards.generator import evaluate_interview_answer, grade_quiz_answer
from mentor.state import record_category_activity
from scheduler.scheduler import get_concept, update_after_review


def submit_quiz(
    *,
    user_id: str,
    concept_id: int,
    question: str,
    expected_answer: str,
    user_answer: str,
    knew_well: bool,
    subject: str,
) -> dict:
    concept = get_concept(concept_id, user_id)
    if not concept:
        raise ValueError(f"Concept {concept_id} not found")

    grade = grade_quiz_answer(question, expected_answer, user_answer, concept["name"])
    verdict = grade.get("verdict", "partial")
    correct = verdict == "correct"
    partial = verdict == "partial"
    update_after_review(concept_id, user_id, correct=correct, partial=partial, easy=knew_well and correct)
    record_category_activity(user_id, concept["category"], subject)
    refreshed = get_concept(concept_id, user_id)
    return {
        "verdict": verdict,
        "feedback": grade.get("feedback", ""),
        "model_used": grade["model_used"],
        "total_cost": grade["total_cost"],
        "recall_strength": refreshed["recall_strength"] if refreshed else None,
    }


def submit_interview_answer(
    *,
    user_id: str,
    concept_id: int,
    question: str,
    answer: str,
    interview_llm_cost: float,
    subject: str,
) -> dict:
    concept = get_concept(concept_id, user_id)
    if not concept:
        raise ValueError(f"Concept {concept_id} not found")

    grade = evaluate_interview_answer(concept["name"], question, answer)
    verdict = grade.get("verdict", "partial")
    if verdict == "correct":
        update_after_review(concept_id, user_id, correct=True)
    elif verdict == "partial":
        update_after_review(concept_id, user_id, correct=False, partial=True)
    else:
        update_after_review(concept_id, user_id, correct=False)
    record_category_activity(user_id, concept["category"], subject)
    refreshed = get_concept(concept_id, user_id)
    return {
        "verdict": verdict,
        "feedback": grade.get("feedback", ""),
        "model_used": grade["model_used"],
        "total_cost": interview_llm_cost + grade["total_cost"],
        "recall_strength": refreshed["recall_strength"] if refreshed else None,
    }
