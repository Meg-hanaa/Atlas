"""Tests for YouTube ingestion caption path and Whisper fallback."""

from unittest.mock import MagicMock, patch

import pytest

from ingest.youtube_ingest import _extract_video_id, ingest_youtube


def test_extract_video_id():
    assert _extract_video_id("https://youtu.be/PIfj8jJuO1s") == "PIfj8jJuO1s"
    assert _extract_video_id("https://www.youtube.com/watch?v=E0Hmnixke2g") == "E0Hmnixke2g"


@patch("ingest.youtube_ingest._fetch_captions")
def test_caption_fast_path(mock_captions):
    mock_captions.return_value = "Hello from captions"
    result = ingest_youtube("https://youtu.be/PIfj8jJuO1s", "ml-notes")
    assert result["transcription_method"] == "captions"
    assert result["content"] == "Hello from captions"
    assert result["source"] == "youtube:PIfj8jJuO1s"


@patch("ingest.youtube_ingest._transcribe_with_whisper")
@patch("ingest.youtube_ingest._fetch_captions")
def test_whisper_fallback_when_no_captions(mock_captions, mock_whisper):
    mock_captions.return_value = None
    mock_whisper.return_value = "Transcribed by whisper"
    result = ingest_youtube("https://youtu.be/NOCCAPTION1", "ml-notes")
    assert result["transcription_method"] == "whisper"
    assert result["content"] == "Transcribed by whisper"
    mock_whisper.assert_called_once()


@patch("ingest.youtube_ingest._fetch_captions")
def test_empty_captions_triggers_whisper(mock_captions):
    mock_captions.return_value = None
    with patch("ingest.youtube_ingest._transcribe_with_whisper", return_value="whisper text"):
        result = ingest_youtube("https://youtu.be/NOCCAPTION1", "ml-notes")
        assert result["transcription_method"] == "whisper"
