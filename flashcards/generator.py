"""Flashcard generation with cascadeflow quality routing, quiz grading, mock interview."""

from __future__ import annotations

import json
import re

from memory.bank import reflect_query, search_memories
from routing.models import (
    cascade_run,
    flashcard_agent,
    grading_agent,
    run_async,
)


def _parse_flashcard(text: str) -> dict:
    question = ""
    answer = ""
    q_match = re.search(r"(?:Q(?:uestion)?|Front)\s*[:.]?\s*(.+?)(?=(?:A(?:nswer)?|Back)\s*[:.]|$)", text, re.I | re.S)
    a_match = re.search(r"(?:A(?:nswer)?|Back)\s*[:.]?\s*(.+)", text, re.I | re.S)
    if q_match:
        question = q_match.group(1).strip()
    if a_match:
        answer = a_match.group(1).strip()
    if not question and not answer:
        parts = text.strip().split("\n---\n", 1)
        if len(parts) == 2:
            question, answer = parts[0].strip(), parts[1].strip()
        else:
            question = text.strip()
    return {"question": question, "answer": answer, "raw": text}


async def _generate_flashcard_async(concept: str, category: str, user_id: str, subject: str) -> dict:
    context = "\n".join(search_memories(user_id, concept, subject=subject, max_results=5))
    prompt = f"""\
Draft a single spaced-repetition flashcard for this ML study concept.

Concept: {concept}
Category: {category}

Use notes context:
{context}

Format exactly:
Question: <clear question testing understanding>
Answer: <concise answer, 2-4 sentences max>
"""
    result = await cascade_run(flashcard_agent(), prompt, max_tokens=300, operation="cascadeflow.flashcard")
    card = _parse_flashcard(result.content)
    card["model_used"] = result.model_used
    card["total_cost"] = result.total_cost
    card["concept"] = concept
    card["category"] = category
    card["cascaded"] = result.cascaded
    card["quality_check_passed"] = result.quality_check_passed
    card["draft_accepted"] = result.draft_accepted
    card["quality_score"] = result.quality_score
    card["draft_confidence"] = result.draft_confidence
    return card


def apply_flashcard_difficulty_signal(concept_id: int, user_id: str, flashcard_result: dict) -> None:
    escalated = flashcard_result.get("cascaded") is True
    quality_failed = flashcard_result.get("quality_check_passed") is False
    if escalated or quality_failed:
        from scheduler.scheduler import apply_generation_escalation_signal

        apply_generation_escalation_signal(concept_id, user_id)


def generate_flashcard(concept: str, category: str, user_id: str, subject: str) -> dict:
    return run_async(_generate_flashcard_async(concept, category, user_id, subject))


async def _grade_answer_async(
    question: str,
    expected: str,
    user_answer: str,
    concept: str,
) -> dict:
    prompt = f"""\
Grade this quiz answer. Reply with JSON only: {{"verdict": "correct"|"partial"|"wrong", "feedback": "..."}}

Concept: {concept}
Question: {question}
Expected answer: {expected}
Student answer: {user_answer}
"""
    result = await cascade_run(grading_agent(), prompt, max_tokens=150, operation="cascadeflow.quiz_grade")
    try:
        match = re.search(r"\{.*\}", result.content, re.S)
        data = json.loads(match.group()) if match else {"verdict": "partial", "feedback": result.content}
    except json.JSONDecodeError:
        data = {"verdict": "partial", "feedback": result.content}
    data["model_used"] = result.model_used
    data["total_cost"] = result.total_cost
    return data


def grade_quiz_answer(question: str, expected: str, user_answer: str, concept: str) -> dict:
    return run_async(_grade_answer_async(question, expected, user_answer, concept))


async def _mock_interview_async(
    concept: str,
    recall_strength: float,
    user_id: str,
    subject: str,
) -> dict:
    mistake_query = (
        f"What does the learner consistently get wrong or confuse about '{concept}'? "
        "List specific misconceptions based on their study history."
    )
    mistakes = reflect_query(user_id, mistake_query, subject=subject, budget="mid")

    if recall_strength > 0.4:
        mode = "quick_check"
        prompt = f"""\
You are a mock ML interviewer. Ask ONE focused question to check understanding of: {concept}

Known weak areas (from memory):
{mistakes}

Reply with just the interview question, no preamble.
"""
    else:
        mode = "reteach"
        prompt = f"""\
You are a patient ML tutor in mock interview mode. The learner struggles with: {concept}
(recall strength {recall_strength:.2f}).

Their recurring mistakes:
{mistakes}

Give a short re-teach (3-5 sentences) addressing those specific confusions, then ask one follow-up question.
"""

    from routing.models import chat_agent

    result = await cascade_run(chat_agent(), prompt, max_tokens=400, operation="cascadeflow.mock_interview")
    return {
        "mode": mode,
        "content": result.content,
        "mistakes": mistakes,
        "model_used": result.model_used,
        "total_cost": result.total_cost,
        "recall_strength": recall_strength,
    }


def run_mock_interview(concept: str, recall_strength: float, user_id: str, subject: str) -> dict:
    return run_async(_mock_interview_async(concept, recall_strength, user_id, subject))


async def _evaluate_interview_answer_async(
    concept: str,
    question: str,
    user_answer: str,
) -> dict:
    prompt = f"""\
Grade this mock interview answer. Reply with JSON only:
{{"verdict": "correct"|"partial"|"wrong", "feedback": "..."}}

Concept: {concept}
Interview question: {question}
Candidate answer: {user_answer}
"""
    result = await cascade_run(grading_agent(), prompt, max_tokens=200, operation="cascadeflow.interview_grade")
    try:
        match = re.search(r"\{.*\}", result.content, re.S)
        data = json.loads(match.group()) if match else {"verdict": "partial", "feedback": result.content}
    except json.JSONDecodeError:
        data = {"verdict": "partial", "feedback": result.content}
    data["model_used"] = result.model_used
    data["total_cost"] = result.total_cost
    return data


def evaluate_interview_answer(concept: str, question: str, user_answer: str) -> dict:
    return run_async(_evaluate_interview_answer_async(concept, question, user_answer))
