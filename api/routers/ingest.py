"""Ingestion routes."""

from __future__ import annotations

import os
import tempfile

from fastapi import APIRouter, File, HTTPException, UploadFile

from api.deps import resolve_subject
from api.schemas import (
    IngestDemoResponse,
    IngestLeetcodeRequest,
    IngestPdfRequest,
    IngestPhotoPathRequest,
    IngestResult,
    IngestYouTubeRequest,
)
from api.services.ingest import ingest_all_demo
from auth.deps import CurrentUser, user_id_from
from ingest.leetcode_ingest import ingest_leetcode
from ingest.pdf_ingest import ingest_pdf
from ingest.photo_ocr_ingest import ingest_photo
from ingest.youtube_ingest import ingest_youtube
from memory.bank import retain_ingested

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/demo", response_model=IngestDemoResponse)
def ingest_demo(user: CurrentUser, subject: str | None = None):
    subj = resolve_subject(subject)
    result = ingest_all_demo(user_id_from(user), subj)
    return IngestDemoResponse(**result)


@router.post("/youtube", response_model=IngestResult)
def ingest_youtube_route(body: IngestYouTubeRequest, user: CurrentUser, subject: str | None = None):
    subj = resolve_subject(subject)
    chunk = ingest_youtube(body.url, subj)
    retain_ingested(user_id_from(user), chunk)
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
    suffix = os.path.splitext(file.filename or "upload.png")[1] or ".png"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        path = tmp.name
    try:
        result = ingest_photo(path, subj, uid)
        if result["status"] == "ok":
            retain_ingested(uid, result["chunk"])
            return {"status": "ok", "source": result["chunk"]["source"], "confidence": result["confidence"]}
        return {
            "status": "queued",
            "queue_id": result["queue_id"],
            "confidence": result["confidence"],
            "reason": result.get("reason"),
        }
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


@router.post("/leetcode", response_model=IngestResult)
def ingest_leetcode_route(body: IngestLeetcodeRequest, user: CurrentUser, subject: str | None = None):
    subj = resolve_subject(subject)
    chunk = ingest_leetcode(body.prompt, subj, title=body.title)
    retain_ingested(user_id_from(user), chunk)
    return IngestResult(source=chunk["source"])
