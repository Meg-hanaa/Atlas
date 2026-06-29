"""Ingestion routes."""

from __future__ import annotations

import logging
import os
import tempfile

from fastapi import APIRouter, File, HTTPException, UploadFile

logger = logging.getLogger(__name__)

from api.deps import resolve_subject
from api.schemas import (
    IngestDemoResponse,
    IngestLeetcodeRequest,
    IngestPdfRequest,
    IngestPhotoPathRequest,
    IngestResult,
    IngestYouTubeRequest,
    JobCreatedResponse,
)
from api.services.ingest import ingest_all_demo
from auth.deps import CurrentUser, user_id_from
from core.jobs import create_job, run_in_background
from ingest.docx_ingest import ingest_docx
from ingest.leetcode_ingest import ingest_leetcode
from ingest.pdf_ingest import ingest_pdf
from ingest.photo_ocr_ingest import ingest_photo
from ingest.youtube_ingest import ingest_youtube
from core.subjects import ensure_subject
from memory.bank import retain_ingested

router = APIRouter(prefix="/ingest", tags=["ingest"])


def _photo_result_payload(result: dict) -> dict:
    if result["status"] == "ok":
        return {"status": "ok", "source": result["chunk"]["source"], "confidence": result["confidence"]}
    return {
        "status": "queued",
        "queue_id": result["queue_id"],
        "confidence": result["confidence"],
        "reason": result.get("reason"),
    }


def _run_photo_ingest(path: str, subj: str, uid: str) -> dict:
    try:
        result = ingest_photo(path, subj, uid, fast=True)
        if result["status"] == "ok":
            retain_ingested(uid, result["chunk"])
        return _photo_result_payload(result)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def _run_document_ingest(path: str, suffix: str, subj: str, uid: str) -> dict:
    try:
        if suffix == ".pdf":
            chunk = ingest_pdf(path, subj)
        elif suffix == ".docx":
            chunk = ingest_docx(path, subj)
        else:
            raise ValueError("Supported types: .pdf, .docx")
        retain_ingested(uid, chunk)
        return {"status": "ok", "source": chunk["source"]}
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


@router.post("/demo", response_model=IngestDemoResponse)
def ingest_demo(user: CurrentUser, subject: str | None = None):
    subj = resolve_subject(subject)
    result = ingest_all_demo(user_id_from(user), subj)
    return IngestDemoResponse(**result)


@router.post("/youtube", response_model=IngestResult)
def ingest_youtube_route(body: IngestYouTubeRequest, user: CurrentUser, subject: str | None = None):
    subj = resolve_subject(subject)
    uid = user_id_from(user)
    ensure_subject(uid, subj)
    try:
        chunk = ingest_youtube(body.url.strip(), subj)
        retain_ingested(uid, chunk)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("YouTube ingest failed")
        raise HTTPException(status_code=500, detail=f"YouTube ingest failed: {exc}") from exc
    return IngestResult(source=chunk["source"])


@router.post("/pdf", response_model=IngestResult)
def ingest_pdf_route(body: IngestPdfRequest, user: CurrentUser, subject: str | None = None):
    subj = resolve_subject(subject)
    if not os.path.isfile(body.path):
        raise HTTPException(status_code=400, detail=f"PDF not found: {body.path}")
    chunk = ingest_pdf(body.path, subj)
    retain_ingested(user_id_from(user), chunk)
    return IngestResult(source=chunk["source"])


@router.post("/pdf/upload", response_model=IngestResult)
async def ingest_pdf_upload(user: CurrentUser, subject: str | None = None, file: UploadFile = File(...)):
    subj = resolve_subject(subject)
    uid = user_id_from(user)
    ensure_subject(uid, subj)
    suffix = os.path.splitext(file.filename or "upload.pdf")[1] or ".pdf"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        path = tmp.name
    try:
        chunk = ingest_pdf(path, subj)
        retain_ingested(uid, chunk)
        return IngestResult(source=chunk["source"])
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


@router.post("/document/upload", response_model=IngestResult)
async def ingest_document_upload(user: CurrentUser, subject: str | None = None, file: UploadFile = File(...)):
    """Upload PDF or Word (.docx) from browser."""
    subj = resolve_subject(subject)
    uid = user_id_from(user)
    ensure_subject(uid, subj)
    suffix = (os.path.splitext(file.filename or "")[1] or ".pdf").lower()
    if suffix not in (".pdf", ".docx"):
        raise HTTPException(status_code=400, detail="Supported types: .pdf, .docx")
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        path = tmp.name
    try:
        return IngestResult(**_run_document_ingest(path, suffix, subj, uid))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Document upload ingest failed")
        raise HTTPException(status_code=500, detail=f"Document ingest failed: {exc}") from exc


@router.post("/document/upload/async", response_model=JobCreatedResponse)
async def ingest_document_upload_async(
    user: CurrentUser, subject: str | None = None, file: UploadFile = File(...)
):
    """Upload PDF/DOCX in a background job (avoids gateway timeouts on Render)."""
    subj = resolve_subject(subject)
    uid = user_id_from(user)
    ensure_subject(uid, subj)
    suffix = (os.path.splitext(file.filename or "")[1] or ".pdf").lower()
    if suffix not in (".pdf", ".docx"):
        raise HTTPException(status_code=400, detail="Supported types: .pdf, .docx")
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        path = tmp.name
    job_id = create_job(uid, "ingest_document", {"subject": subj, "suffix": suffix})
    run_in_background(job_id, lambda: _run_document_ingest(path, suffix, subj, uid))
    return JobCreatedResponse(job_id=job_id)


@router.post("/photo", response_model=dict)
def ingest_photo_route(body: IngestPhotoPathRequest, user: CurrentUser, subject: str | None = None):
    subj = resolve_subject(subject)
    uid = user_id_from(user)
    if not os.path.isfile(body.path):
        raise HTTPException(status_code=400, detail=f"Photo not found: {body.path}")
    result = ingest_photo(body.path, subj, uid)
    if result["status"] == "ok":
        retain_ingested(uid, result["chunk"])
        return {"status": "ok", "source": result["chunk"]["source"], "confidence": result["confidence"]}
    return {
        "status": "queued",
        "queue_id": result["queue_id"],
        "confidence": result["confidence"],
        "reason": result.get("reason"),
    }


@router.post("/photo/upload", response_model=dict)
async def ingest_photo_upload(user: CurrentUser, subject: str | None = None, file: UploadFile = File(...)):
    subj = resolve_subject(subject)
    uid = user_id_from(user)
    ensure_subject(uid, subj)
    suffix = os.path.splitext(file.filename or "upload.png")[1] or ".png"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        path = tmp.name
    try:
        return _run_photo_ingest(path, subj, uid)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc) or "OCR unavailable — set OPENAI_API_KEY, ANTHROPIC_API_KEY, or GROQ_API_KEY on the API service.",
        ) from exc
    except Exception as exc:
        logger.exception("Photo upload ingest failed")
        raise HTTPException(status_code=500, detail=f"Photo ingest failed: {exc}") from exc


@router.post("/photo/upload/async", response_model=JobCreatedResponse)
async def ingest_photo_upload_async(
    user: CurrentUser, subject: str | None = None, file: UploadFile = File(...)
):
    """OCR an uploaded image in a background job (avoids gateway timeouts on Render)."""
    subj = resolve_subject(subject)
    uid = user_id_from(user)
    ensure_subject(uid, subj)
    suffix = os.path.splitext(file.filename or "upload.png")[1] or ".png"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        path = tmp.name
    job_id = create_job(uid, "ingest_photo", {"subject": subj})
    run_in_background(job_id, lambda: _run_photo_ingest(path, subj, uid))
    return JobCreatedResponse(job_id=job_id)


@router.post("/leetcode", response_model=IngestResult)
def ingest_leetcode_route(body: IngestLeetcodeRequest, user: CurrentUser, subject: str | None = None):
    subj = resolve_subject(subject)
    uid = user_id_from(user)
    ensure_subject(uid, subj)
    chunk = ingest_leetcode(body.prompt, subj, title=None)
    retain_ingested(uid, chunk)
    return IngestResult(source=chunk["source"])
