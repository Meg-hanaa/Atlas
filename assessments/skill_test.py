"""Category-spanning skill assessments (strong model grading only)."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone

from cascadeflow import CascadeAgent, ModelConfig

from config import ensure_groq_key, get_subject
from memory.bank import reflect_query, search_memories
from routing.models import STRONG_COST, STRONG_MODEL, run_async
from scheduler.scheduler import list_concepts


def _strong_agent() -> CascadeAgent:
    return CascadeAgent(
        models=[
            ModelConfig(
                name=STRONG_MODEL,
                provider="groq",
                cost=STRONG_COST,
                api_key=ensure_groq_key(),
            )
        ],
    )


def _parse_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.S)
    if match:
        return json.loads(match.group())
    return json.loads(text)


async def _generate_questions_async(
    user_id: str,
    subject: str,
    category: str,
    num_questions: int,
) -> dict:
    concepts = [c for c in list_concepts(user_id, subject) if c["category"] == category]
    if not concepts:
        raise ValueError(f"No concepts in category '{category}'")

    context = reflect_query(
        user_id,
        f"Summarize key facts about {category} from my notes for an assessment.",
        subject=subject,
        budget="mid",
    )
    names = ", ".join(c["name"] for c in concepts[:20])
    prompt = f"""\
Create a {num_questions}-question skill assessment for category: {category}

Concepts covered: {names}

Notes context:
{context}

Return JSON only:
{{
  "questions": [
    {{"id": "q1", "question": "...", "rubric": "what a complete answer must include"}}
  ]
}}
Mix difficulty: some recall, some application. No trick questions.
"""
    agent = _strong_agent()
    result = await agent.run(prompt, max_tokens=1200)
    data = _parse_json(result.content)
    assessment_id = uuid.uuid4().hex
    return {
        "assessment_id": assessment_id,
        "category": category,
        "subject": get_subject(subject),
        "questions": data.get("questions", [])[:num_questions],
        "model_used": result.model_used,
        "total_cost": result.total_cost,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_assessment(
    user_id: str,
    subject: str,
    category: str,
    num_questions: int = 7,
) -> dict:
    n = max(5, min(10, num_questions))
    return run_async(_generate_questions_async(user_id, subject, category, n))


async def _grade_assessment_async(
    user_id: str,
    subject: str,
    assessment: dict,
    answers: dict[str, str],
) -> dict:
    graded = []
    total_cost = 0.0
    model_used = STRONG_MODEL
    agent = _strong_agent()

    for q in assessment.get("questions", []):
        qid = q["id"]
        user_ans = answers.get(qid, "").strip()
        memories = search_memories(user_id, q["question"], subject=subject, max_results=3)
        prompt = f"""\
Grade this assessment answer strictly. Return JSON only:
{{"score": 0-100, "verdict": "pass"|"partial"|"fail", "feedback": "..."}}

Question: {q['question']}
Rubric: {q.get('rubric', '')}
Student answer: {user_ans or '(blank)'}
Relevant notes:
{chr(10).join(memories)}
"""
        result = await agent.run(prompt, max_tokens=250)
        total_cost += result.total_cost
        model_used = result.model_used
        try:
            g = _parse_json(result.content)
        except json.JSONDecodeError:
            g = {"score": 0, "verdict": "fail", "feedback": result.content}
        graded.append({"question_id": qid, "question": q["question"], **g})

    scores = [g.get("score", 0) for g in graded]
    avg = sum(scores) / max(1, len(scores))
    passed = avg >= 70 and all(g.get("verdict") != "fail" for g in graded)

    return {
        "assessment_id": assessment.get("assessment_id"),
        "category": assessment.get("category"),
        "average_score": round(avg, 1),
        "passed": passed,
        "verdict": "PASS" if passed else "FAIL",
        "graded": graded,
        "model_used": model_used,
        "total_cost": total_cost,
    }


def grade_assessment(user_id: str, subject: str, assessment: dict, answers: dict[str, str]) -> dict:
    return run_async(_grade_assessment_async(user_id, subject, assessment, answers))
