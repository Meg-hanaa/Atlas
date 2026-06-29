"""Ingest orchestration service."""

from __future__ import annotations

import os

from ingest.leetcode_ingest import ingest_leetcode
from ingest.pdf_ingest import ingest_pdf
from ingest.photo_ocr_ingest import ingest_photo
from ingest.youtube_ingest import ingest_youtube
from memory.bank import retain_ingested
from sample_sources import DEMO_PDF_PATH, DEMO_PHOTO_PATHS, DEMO_YOUTUBE_URLS, SAMPLE_LEETCODE

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def process_photo_result(result: dict) -> dict | None:
    if result["status"] == "ok":
        return result["chunk"]
    return None


def ingest_all_demo(user_id: str, subject: str) -> dict:
    chunks = []
    errors = []
    queued = 0

    for url in DEMO_YOUTUBE_URLS:
        try:
            chunks.append(ingest_youtube(url, subject))
        except Exception as e:
            errors.append(f"YouTube {url}: {e}")

    if os.path.isfile(DEMO_PDF_PATH):
        try:
            chunks.append(ingest_pdf(DEMO_PDF_PATH, subject))
        except Exception as e:
            errors.append(f"PDF: {e}")
    else:
        errors.append(f"PDF not found: {DEMO_PDF_PATH}")

    for path in DEMO_PHOTO_PATHS:
        full = os.path.join(ROOT, path) if not os.path.isabs(path) else path
        if os.path.isfile(full):
            try:
                photo_result = ingest_photo(full, subject, user_id)
                chunk = process_photo_result(photo_result)
                if chunk:
                    chunks.append(chunk)
                else:
                    queued += 1
            except Exception as e:
                errors.append(f"Photo {path}: {e}")
        else:
            errors.append(f"Photo not found: {path}")

    for item in SAMPLE_LEETCODE:
        chunks.append(ingest_leetcode(item["prompt"], subject, title=item["title"]))

    for chunk in chunks:
        retain_ingested(user_id, chunk)

    return {"retained_count": len(chunks), "errors": errors, "queued_photos": queued}
