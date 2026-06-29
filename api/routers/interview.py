"""Mock interview routes."""

from __future__ import annotations

import base64

from fastapi import APIRouter, HTTPException

from api.deps import resolve_subject
from api.schemas import InterviewAnswerRequest, InterviewStartRequest, InterviewStartResponse, QuizSubmitResponse
from api.services.study import submit_interview_answer
from auth.deps import CurrentUser, user_id_from
from flashcards.generator import run_mock_interview
from scheduler.scheduler import get_concept
from voice.tts import ensure_voice_model, synthesize_wav_bytes

router = APIRouter(prefix="/mock-interview", tags=["interview"])


@router.post("/{subject}/start", response_model=InterviewStartResponse)
def interview_start(subject: str, body: InterviewStartRequest, user: CurrentUser):
    subj = resolve_subject(subject)
    uid = user_id_from(user)
    concept = get_concept(body.concept_id, uid)
    if not concept:
        raise HTTPException(status_code=404, detail="Concept not found")

    step = run_mock_interview(concept["name"], concept["recall_strength"], uid, subj)
    audio_b64 = None
    tts_chars = None
    if body.voice:
        ensure_voice_model()
        tts = synthesize_wav_bytes(step["content"])
        audio_b64 = base64.b64encode(tts["audio_bytes"]).decode("ascii")
        tts_chars = tts["chars"]

    return InterviewStartResponse(
        mode=step["mode"],
        content=step["content"],
        mistakes=step["mistakes"],
        model_used=step["model_used"],
        total_cost=step["total_cost"],
        recall_strength=step["recall_strength"],
        concept_id=concept["id"],
        concept_name=concept["name"],
        category=concept["category"],
        audio_base64=audio_b64,
        tts_chars=tts_chars,
    )


@router.post("/{subject}/answer", response_model=QuizSubmitResponse)
def interview_answer(subject: str, body: InterviewAnswerRequest, user: CurrentUser):
    subj = resolve_subject(subject)
    uid = user_id_from(user)
    try:
        result = submit_interview_answer(
            user_id=uid,
            concept_id=body.concept_id,
            question=body.question,
            answer=body.answer,
            interview_llm_cost=body.interview_llm_cost,
            subject=subj,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    feedback_audio = None
    if body.voice_feedback and result.get("feedback"):
        try:
            ensure_voice_model()
            tts = synthesize_wav_bytes(result["feedback"][:500])
            feedback_audio = base64.b64encode(tts["audio_bytes"]).decode("ascii")
        except Exception:
            feedback_audio = None

    return QuizSubmitResponse(**result, feedback_audio_base64=feedback_audio)
