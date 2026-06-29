"""Ingest handwritten notes via vision-LLM OCR with confidence scoring."""

from __future__ import annotations

import difflib
import logging
import os
import re
from datetime import datetime, timezone

from monitoring.tracing import set_span_attributes, trace_span

logger = logging.getLogger(__name__)

OCR_PROMPT = (
    "Transcribe all handwritten text from this study note image. "
    "Preserve headings, bullet points, equations, and diagram labels. "
    "Return plain text only — no commentary."
)

OCR_PROMPT_ALT = (
    "Independently transcribe every word of handwritten text in this image. "
    "Be literal — include headings, formulas, and labels. Plain text only."
)

GROQ_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
CONFIDENCE_THRESHOLD = float(os.getenv("ATLAS_OCR_CONFIDENCE_THRESHOLD", "0.75"))


def _encode_image(path: str) -> tuple[str, str]:
    import base64

    ext = os.path.splitext(path)[1].lower()
    media = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(ext, "image/jpeg")
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8"), media


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def _ocr_openai(path: str, api_key: str, prompt: str) -> str:
    from openai import OpenAI

    b64, media_type = _encode_image(path)
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{media_type};base64,{b64}"},
                    },
                ],
            }
        ],
        max_tokens=2048,
    )
    return response.choices[0].message.content or ""


def _ocr_anthropic(path: str, api_key: str, prompt: str) -> str:
    from anthropic import Anthropic

    b64, media_type = _encode_image(path)
    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )
    return response.content[0].text


def _ocr_groq(path: str, api_key: str, prompt: str) -> str:
    from groq import Groq

    b64, media_type = _encode_image(path)
    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=GROQ_VISION_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{media_type};base64,{b64}"},
                    },
                ],
            }
        ],
        max_tokens=2048,
    )
    return response.choices[0].message.content or ""


def _vision_call(path: str, prompt: str, prefer_groq: bool = False) -> str:
    """Single vision OCR call; tries providers in order."""
    errors: list[str] = []

    openai_key = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    order: list[tuple[str, str | None]]
    groq_key = os.getenv("GROQ_API_KEY")
    groq_key = groq_key if groq_key and not groq_key.startswith("your-") else None

    if prefer_groq:
        order = [
            ("groq", groq_key),
            ("openai", openai_key if openai_key and not openai_key.startswith("your-") else None),
            ("anthropic", anthropic_key if anthropic_key and not anthropic_key.startswith("your-") else None),
        ]
    else:
        order = [
            ("openai", openai_key if openai_key and not openai_key.startswith("your-") else None),
            ("anthropic", anthropic_key if anthropic_key and not anthropic_key.startswith("your-") else None),
            ("groq", groq_key),
        ]

    for provider, key in order:
        if not key:
            continue
        try:
            if provider == "openai":
                return _ocr_openai(path, key, prompt)
            if provider == "anthropic":
                return _ocr_anthropic(path, key, prompt)
            return _ocr_groq(path, key, prompt)
        except Exception as e:
            errors.append(f"{provider}: {e}")

    raise RuntimeError("All vision OCR providers failed: " + " | ".join(errors))


def score_ocr_confidence(primary: str, secondary: str) -> tuple[float, str]:
    """Dual-pass agreement score."""
    ratio = _similarity(primary, secondary)
    if ratio >= CONFIDENCE_THRESHOLD:
        reason = "dual_pass_agreement"
    else:
        reason = f"dual_pass_disagreement (similarity={ratio:.2f})"
    return ratio, reason


def ingest_photo(path: str, subject: str, user_id: str, *, fast: bool = False) -> dict:
    """
    OCR a handwritten note with dual-pass confidence scoring.

    When fast=True (browser uploads), run a single vision call to stay within
    gateway timeouts; empty or very short text is queued for review.

    Returns either:
      {"status": "ok", "chunk": {...}, "confidence": float}
    or:
      {"status": "needs_review", "queue_id": int, "confidence": float, "reason": str, ...}
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Photo not found: {path}")

    with trace_span("ingest.photo_ocr", {"path": path, "subject": subject, "fast": fast}) as span:
        logger.info("OCR pass 1", extra={"path": path, "ingest": "photo", "fast": fast})
        primary = _vision_call(path, OCR_PROMPT, prefer_groq=False)

        if fast:
            stripped = primary.strip()
            if len(stripped) >= 20:
                confidence, reason = 1.0, "upload_single_pass"
                secondary = primary
            else:
                confidence, reason = 0.0, "upload_single_pass_empty"
                secondary = ""
        else:
            logger.info("OCR pass 2 (independent)", extra={"path": path, "ingest": "photo"})
            secondary = _vision_call(path, OCR_PROMPT_ALT, prefer_groq=True)
            confidence, reason = score_ocr_confidence(primary, secondary)
        source = f"photo:{os.path.basename(path)}"
        date = datetime.now(timezone.utc).isoformat()

        set_span_attributes(
            span,
            ocr_confidence=confidence,
            ocr_reason=reason,
            status="ok" if confidence >= CONFIDENCE_THRESHOLD else "needs_review",
        )

    logger.info(
        "OCR confidence=%.2f for %s",
        confidence,
        source,
        extra={"path": path, "confidence": confidence, "reason": reason},
    )

    if confidence < CONFIDENCE_THRESHOLD:
        from review.queue import enqueue

        queue_id = enqueue(
            user_id,
            subject=subject,
            source=source,
            path=path,
            transcription=primary,
            alt_transcription=secondary,
            confidence=confidence,
            reason=reason,
        )
        return {
            "status": "needs_review",
            "queue_id": queue_id,
            "subject": subject,
            "source": source,
            "path": path,
            "transcription": primary,
            "alt_transcription": secondary,
            "confidence": confidence,
            "reason": reason,
        }

    return {
        "status": "ok",
        "confidence": confidence,
        "chunk": {
            "subject": subject,
            "source": source,
            "content": primary,
            "date": date,
            "ocr_confidence": confidence,
        },
    }
