"""Streamlit HTTP client for the Atlas FastAPI backend."""

from __future__ import annotations

import base64
import os
from typing import Any

import httpx

DEFAULT_API_URL = os.getenv("ATLAS_API_URL", "http://127.0.0.1:8000")


class AtlasApiError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"API {status_code}: {detail}")


class AtlasClient:
    def __init__(self, base_url: str | None = None, session_id: str | None = None, token: str | None = None):
        self.base_url = (base_url or DEFAULT_API_URL).rstrip("/")
        self.session_id = session_id
        self.token = token
        self._client = httpx.Client(base_url=self.base_url, timeout=300.0)

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.session_id:
            headers["X-Session-Id"] = self.session_id
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _params(self, subject: str | None = None, **extra) -> dict[str, Any]:
        params = dict(extra)
        if subject:
            params["subject"] = subject
        return params

    def _handle(self, resp: httpx.Response) -> Any:
        if resp.is_success:
            if resp.headers.get("content-type", "").startswith("application/json"):
                return resp.json()
            return resp.content
        detail = resp.text
        try:
            detail = resp.json().get("detail", detail)
        except Exception:
            pass
        raise AtlasApiError(resp.status_code, str(detail))

    def _call(self, method: str, url: str, **kwargs) -> Any:
        headers = {**self._headers(), **kwargs.pop("headers", {})}
        resp = getattr(self._client, method)(url, headers=headers, **kwargs)
        return self._handle(resp)

    def login(self, email: str, password: str) -> str:
        resp = self._client.post(
            "/auth/jwt/login",
            data={"username": email, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        return self._handle(resp)["access_token"]

    def register(self, email: str, password: str) -> dict:
        return self._handle(
            self._client.post("/auth/register", json={"email": email, "password": password})
        )

    def forgot_password(self, email: str) -> None:
        self._call("post", "/auth/forgot-password", json={"email": email})

    def reset_password(self, token: str, password: str) -> None:
        self._call("post", "/auth/reset-password", json={"token": token, "password": password})

    def verify_email(self, token: str) -> None:
        self._call("post", "/auth/verify", json={"token": token})

    def request_verify(self, email: str) -> None:
        self._call("post", "/auth/request-verify-token", json={"email": email})

    def health(self, subject: str | None = None) -> dict:
        return self._call("get", "/health", params=self._params(subject))

    def ingest_demo(self, subject: str | None = None) -> dict:
        return self._call("post", "/ingest/demo", params=self._params(subject))

    def ingest_youtube(self, url: str, subject: str | None = None) -> dict:
        return self._call("post", "/ingest/youtube", params=self._params(subject), json={"url": url})

    def ingest_pdf(self, path: str, subject: str | None = None) -> dict:
        return self._call("post", "/ingest/pdf", params=self._params(subject), json={"path": path})

    def ingest_photo(self, path: str, subject: str | None = None) -> dict:
        return self._call("post", "/ingest/photo", params=self._params(subject), json={"path": path})

    def ingest_leetcode(self, prompt: str, title: str | None = None, subject: str | None = None) -> dict:
        return self._call(
            "post",
            "/ingest/leetcode",
            params=self._params(subject),
            json={"prompt": prompt, "title": title},
        )

    def review_list(self, subject: str | None = None) -> list:
        return self._call("get", "/review-queue", params=self._params(subject))

    def review_approve(self, item_id: int, edited_text: str | None = None, subject: str | None = None) -> dict:
        return self._call(
            "post",
            f"/review-queue/{item_id}/approve",
            params=self._params(subject),
            json={"edited_text": edited_text},
        )

    def review_reject(self, item_id: int) -> dict:
        return self._call("post", f"/review-queue/{item_id}/reject")

    def seed_concepts(self, subject: str | None = None) -> dict:
        return self._call("post", "/concepts/seed", params=self._params(subject))

    def seed_demo_reviews(self, subject: str | None = None) -> dict:
        return self._call("post", "/concepts/seed-demo-reviews", params=self._params(subject))

    def revision_today(self, subject: str | None = None) -> dict:
        return self._call("get", "/revision/today", params=self._params(subject))

    def mentor_nudges(self, subject: str | None = None) -> list:
        return self._call("get", "/mentor/nudges", params=self._params(subject))

    def mentor_acknowledge(self, category: str, subject: str | None = None) -> dict:
        return self._call(
            "post",
            "/mentor/nudges/acknowledge",
            params=self._params(subject),
            json={"category": category},
        )

    def list_concepts(self, subject: str | None = None) -> list:
        return self._call("get", "/concepts", params=self._params(subject))

    def weak_concepts(self, subject: str | None = None, threshold: float = 0.6) -> list:
        return self._call("get", "/concepts/weak", params=self._params(subject, threshold=threshold))

    def get_notes(self, subject: str) -> str:
        return self._call("get", f"/notes/{subject}")["markdown"]

    def get_notes_async(self, subject: str) -> str:
        job_id = self._call("post", f"/notes/{subject}/async")["job_id"]
        return self.wait_for_job(job_id)["markdown"]

    def wait_for_job(self, job_id: str, poll_seconds: float = 1.0, timeout: float = 600.0) -> dict:
        import time

        deadline = time.time() + timeout
        while time.time() < deadline:
            job = self._call("get", f"/jobs/{job_id}")
            if job["status"] == "completed":
                return job["result"] or {}
            if job["status"] == "failed":
                raise AtlasApiError(500, job.get("error") or "Background job failed")
            time.sleep(poll_seconds)
        raise AtlasApiError(504, "Background job timed out")

    def roadmap_diff(self, subject: str) -> dict:
        return self._call("get", f"/roadmap/{subject}/diff")

    def roadmap_narrative(self, subject: str) -> str:
        return self._call("post", f"/roadmap/{subject}/narrative")["markdown"]

    def roadmap_narrative_async(self, subject: str) -> str:
        job_id = self._call("post", f"/roadmap/{subject}/narrative/async")["job_id"]
        return self.wait_for_job(job_id)["markdown"]

    def graph_prerequisites(self, subject: str) -> dict:
        return self._call("post", f"/graph/{subject}/prerequisites")

    def graph_prerequisites_async(self, subject: str) -> dict:
        job_id = self._call("post", f"/graph/{subject}/prerequisites/async")["job_id"]
        return self.wait_for_job(job_id)

    def search(self, q: str, subject: str | None = None) -> list[str]:
        return self._call("get", "/search", params=self._params(subject, q=q))["results"]

    def chat(self, question: str, subject: str | None = None) -> dict:
        return self._call("post", "/chat", params=self._params(subject), json={"question": question})

    def concepts_by_category(self, subject: str | None = None) -> dict:
        return self._call("get", "/concepts/by-category", params=self._params(subject))

    def cross_category_reflect(
        self,
        category_a: str,
        concept_a: str,
        category_b: str,
        concept_b: str,
        subject: str | None = None,
    ) -> str:
        return self._call(
            "post",
            "/reflect/cross-category",
            params=self._params(subject),
            json={
                "category_a": category_a,
                "concept_a": concept_a,
                "category_b": category_b,
                "concept_b": concept_b,
            },
        )["markdown"]

    def generate_flashcard(self, subject: str, concept_id: int) -> dict:
        return self._call(
            "post",
            f"/flashcards/{subject}/generate",
            json={"concept_id": concept_id},
        )

    def submit_quiz(
        self,
        *,
        concept_id: int,
        question: str,
        expected_answer: str,
        user_answer: str,
        knew_well: bool,
        subject: str | None = None,
    ) -> dict:
        return self._call(
            "post",
            "/quiz/answer",
            params=self._params(subject),
            json={
                "concept_id": concept_id,
                "question": question,
                "expected_answer": expected_answer,
                "user_answer": user_answer,
                "knew_well": knew_well,
            },
        )

    def interview_start(self, subject: str, concept_id: int, voice: bool = False) -> dict:
        return self._call(
            "post",
            f"/mock-interview/{subject}/start",
            json={"concept_id": concept_id, "voice": voice},
        )

    def interview_answer(
        self,
        subject: str,
        *,
        concept_id: int,
        question: str,
        answer: str,
        interview_llm_cost: float = 0.0,
        voice_feedback: bool = False,
    ) -> dict:
        return self._call(
            "post",
            f"/mock-interview/{subject}/answer",
            json={
                "concept_id": concept_id,
                "question": question,
                "answer": answer,
                "interview_llm_cost": interview_llm_cost,
                "voice_feedback": voice_feedback,
            },
        )

    def transcribe_audio(self, data: bytes, filename: str = "answer.wav") -> dict:
        return self._call(
            "post",
            "/voice/stt",
            files={"file": (filename, data, "application/octet-stream")},
        )

    def analytics_dashboard(self, subject: str) -> dict:
        return self._call("get", f"/analytics/{subject}/dashboard")

    def assessment_categories(self, subject: str) -> list[str]:
        return self._call("get", f"/assessments/{subject}/categories")["categories"]

    def generate_assessment(self, subject: str, category: str, num_questions: int = 7) -> dict:
        return self._call(
            "post",
            f"/assessments/{subject}/generate",
            json={"category": category, "num_questions": num_questions},
        )

    def grade_assessment(self, subject: str, assessment: dict, answers: dict[str, str]) -> dict:
        return self._call(
            "post",
            f"/assessments/{subject}/grade",
            json={"assessment": assessment, "answers": answers},
        )

    def export_pdf(self, subject: str) -> bytes:
        return self._call("get", f"/export/{subject}/pdf")

    def export_obsidian(self, subject: str) -> bytes:
        return self._call("get", f"/export/{subject}/obsidian")

    def export_anki(self, subject: str) -> bytes:
        return self._call("get", f"/export/{subject}/anki")

    @staticmethod
    def decode_audio(b64: str) -> bytes:
        return base64.b64decode(b64)
