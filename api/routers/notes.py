"""Notes, search, and chat routes."""

from __future__ import annotations

from fastapi import APIRouter

from api.deps import resolve_subject
from api.schemas import ChatRequest, ChatResponse, JobCreatedResponse, NotesResponse, SearchResponse
from api.services.chat import chat_with_notes
from auth.deps import CurrentUser, user_id_from
from core.jobs import create_job, run_in_background
from memory.bank import consolidated_notes, search_memories

router = APIRouter(tags=["notes"])


@router.get("/notes/{subject}", response_model=NotesResponse)
def get_notes(subject: str, user: CurrentUser):
    subj = resolve_subject(subject)
    return NotesResponse(markdown=consolidated_notes(user_id_from(user), subj))


@router.post("/notes/{subject}/async", response_model=JobCreatedResponse)
def generate_notes_async(subject: str, user: CurrentUser):
    subj = resolve_subject(subject)
    uid = user_id_from(user)
    job_id = create_job(uid, "notes", {"subject": subj})
    run_in_background(job_id, lambda: {"markdown": consolidated_notes(uid, subj)})
    return JobCreatedResponse(job_id=job_id)


@router.get("/search", response_model=SearchResponse)
def search(q: str, user: CurrentUser, subject: str | None = None):
    subj = resolve_subject(subject)
    return SearchResponse(results=search_memories(user_id_from(user), q, subject=subj))


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, user: CurrentUser, subject: str | None = None):
    subj = resolve_subject(subject)
    result = await chat_with_notes(user_id_from(user), body.question, subj)
    return ChatResponse(**result)
