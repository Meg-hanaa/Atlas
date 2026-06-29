"""Pydantic request/response models for the Atlas API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    subject: str
    hindsight_ok: bool


class IngestYouTubeRequest(BaseModel):
    url: str


class IngestPdfRequest(BaseModel):
    path: str


class IngestLeetcodeRequest(BaseModel):
    prompt: str
    title: str | None = None


class IngestPhotoPathRequest(BaseModel):
    path: str


class IngestResult(BaseModel):
    source: str
    retained: bool = True


class IngestDemoResponse(BaseModel):
    retained_count: int
    queued_photos: int
    errors: list[str]


class SearchResponse(BaseModel):
    results: list[str]


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str
    model_used: str
    total_cost: float
    memories: list[str]
    grounded: bool


class NotesResponse(BaseModel):
    markdown: str


class ConceptReviewRequest(BaseModel):
    correct: bool = False
    partial: bool = False
    easy: bool = False


class FlashcardGenerateRequest(BaseModel):
    concept_id: int


class QuizSubmitRequest(BaseModel):
    concept_id: int
    question: str
    expected_answer: str
    user_answer: str
    knew_well: bool = False


class QuizSubmitResponse(BaseModel):
    verdict: str
    feedback: str
    model_used: str
    total_cost: float
    recall_strength: float | None = None
    feedback_audio_base64: str | None = None


class InterviewStartRequest(BaseModel):
    concept_id: int
    voice: bool = False


class InterviewStartResponse(BaseModel):
    mode: str
    content: str
    mistakes: str
    model_used: str
    total_cost: float
    recall_strength: float
    concept_id: int
    concept_name: str
    category: str
    audio_base64: str | None = None
    tts_chars: int | None = None


class InterviewAnswerRequest(BaseModel):
    concept_id: int
    question: str
    answer: str
    interview_llm_cost: float = 0.0
    voice_feedback: bool = False


class CrossCategoryRequest(BaseModel):
    category_a: str
    concept_a: str
    category_b: str
    concept_b: str


class ReviewApproveRequest(BaseModel):
    edited_text: str | None = None


class TtsRequest(BaseModel):
    text: str


class TtsResponse(BaseModel):
    audio_base64: str
    mime: str
    chars: int
    cost_usd: float


class SttResponse(BaseModel):
    text: str
    duration_seconds: float
    model: str
    cost_usd: float


class SeedConceptsResponse(BaseModel):
    seeded: int


class MentorAckRequest(BaseModel):
    category: str


class JobCreatedResponse(BaseModel):
    job_id: str
