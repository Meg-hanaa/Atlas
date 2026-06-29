"""Ingest YouTube video captions via youtube-transcript-api, with faster-whisper fallback."""

from __future__ import annotations

import logging
import os
import re
import tempfile
from datetime import datetime, timezone

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

from monitoring.events import set_span_attributes, trace_span

logger = logging.getLogger(__name__)

WHISPER_MODEL_SIZE = os.getenv("ATLAS_WHISPER_MODEL", "base")


def _extract_video_id(url: str) -> str:
    patterns = [
        r"(?:v=|/)([0-9A-Za-z_-]{11}).*",
        r"youtu\.be/([0-9A-Za-z_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    if re.fullmatch(r"[0-9A-Za-z_-]{11}", url):
        return url
    raise ValueError(f"Could not parse YouTube video ID from: {url}")


def _fetch_captions(video_id: str) -> str | None:
    """Return caption text, or None if captions are unavailable."""
    api = YouTubeTranscriptApi()
    try:
        fetched = api.fetch(video_id)
    except (TranscriptsDisabled, NoTranscriptFound):
        logger.info(
            "No captions for video %s — will try Whisper fallback",
            video_id,
            extra={"video_id": video_id, "ingest": "youtube"},
        )
        return None
    except VideoUnavailable as exc:
        raise ValueError(f"Video unavailable: {video_id}") from exc

    content = "\n".join(snippet.text for snippet in fetched.snippets)
    return content if content.strip() else None


def _download_audio(video_id: str) -> str:
    """Download video audio to a temp file; return path to audio."""
    import yt_dlp

    tmpdir = tempfile.mkdtemp(prefix="atlas_yt_")
    out_template = os.path.join(tmpdir, f"{video_id}.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": out_template,
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }
        ],
    }

    url = f"https://www.youtube.com/watch?v={video_id}"
    logger.info(
        "Downloading audio for Whisper transcription",
        extra={"video_id": video_id, "url": url, "ingest": "youtube"},
    )

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    for name in os.listdir(tmpdir):
        if name.startswith(video_id):
            return os.path.join(tmpdir, name)

    raise RuntimeError(f"Audio download failed for {video_id}")


def _transcribe_audio(audio_path: str) -> str:
    """Transcribe audio locally with faster-whisper."""
    from faster_whisper import WhisperModel

    logger.info(
        "Transcribing with faster-whisper model=%s",
        WHISPER_MODEL_SIZE,
        extra={"audio_path": audio_path, "ingest": "youtube"},
    )

    model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(audio_path, beam_size=5)
    lines = [segment.text.strip() for segment in segments if segment.text.strip()]
    return "\n".join(lines)


def _transcribe_with_whisper(video_id: str) -> str:
    audio_path = _download_audio(video_id)
    try:
        content = _transcribe_audio(audio_path)
    finally:
        # Clean up temp dir
        parent = os.path.dirname(audio_path)
        try:
            os.remove(audio_path)
            os.rmdir(parent)
        except OSError:
            pass

    if not content.strip():
        raise ValueError(f"Whisper returned empty transcript for {video_id}")
    return content


def ingest_youtube(url: str, subject: str) -> dict:
    """
    Fetch captions (fast path) or fall back to local Whisper transcription.

    Returns: {"subject", "source", "content", "date", "transcription_method"}
    """
    video_id = _extract_video_id(url)
    source = f"youtube:{video_id}"

    with trace_span(
        "ingest.youtube",
        {"video_id": video_id, "url": url, "subject": subject},
    ) as span:
        content = _fetch_captions(video_id)
        method = "captions"

        if content is None:
            logger.warning(
                "Caption fetch failed for %s — falling back to faster-whisper",
                video_id,
                extra={"video_id": video_id, "url": url, "ingest": "youtube"},
            )
            content = _transcribe_with_whisper(video_id)
            method = "whisper"
        else:
            logger.info(
                "Using YouTube captions for %s",
                video_id,
                extra={"video_id": video_id, "ingest": "youtube", "method": "captions"},
            )

        set_span_attributes(
            span,
            transcription_method=method,
            content_length=len(content),
        )

    return {
        "subject": subject,
        "source": source,
        "content": content,
        "date": datetime.now(timezone.utc).isoformat(),
        "transcription_method": method,
    }
