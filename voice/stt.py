"""Speech-to-text via local faster-whisper."""

from __future__ import annotations

import logging
import os
import tempfile
from functools import lru_cache

logger = logging.getLogger(__name__)

WHISPER_MODEL_SIZE = os.getenv("ATLAS_WHISPER_MODEL", "base")


@lru_cache(maxsize=1)
def _whisper_model():
    from faster_whisper import WhisperModel

    logger.info("Loading faster-whisper model=%s", WHISPER_MODEL_SIZE)
    return WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")


def transcribe_file(audio_path: str, *, beam_size: int = 5) -> dict:
    """Transcribe an audio file. Returns text and approximate duration seconds."""
    model = _whisper_model()
    segments, info = model.transcribe(audio_path, beam_size=beam_size)
    lines = [segment.text.strip() for segment in segments if segment.text.strip()]
    text = " ".join(lines).strip()
    duration = float(getattr(info, "duration", 0.0) or 0.0)
    return {
        "text": text,
        "duration_seconds": duration,
        "model": f"faster-whisper/{WHISPER_MODEL_SIZE}",
        "cost_usd": 0.0,
    }


def transcribe_bytes(data: bytes, suffix: str = ".wav", **kwargs) -> dict:
    """Write bytes to a temp file and transcribe."""
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        path = tmp.name
    try:
        return transcribe_file(path, **kwargs)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
