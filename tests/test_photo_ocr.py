"""Tests for OCR confidence scoring and review queue."""

from unittest.mock import patch

from ingest.photo_ocr_ingest import ingest_photo, score_ocr_confidence
from review.queue import list_pending
from tests.conftest import TEST_USER_ID

UID = TEST_USER_ID


def test_high_confidence_identical_passes():
    conf, reason = score_ocr_confidence("same text", "same text")
    assert conf >= 0.75
    assert "agreement" in reason


def test_low_confidence_divergent_passes():
    conf, _ = score_ocr_confidence(
        "gradient descent minimizes loss",
        "decision trees split on entropy",
    )
    assert conf < 0.75


@patch("ingest.photo_ocr_ingest._vision_call")
def test_low_confidence_queues_for_review(mock_vision, tmp_path):
    img = tmp_path / "note.png"
    img.write_bytes(b"fake")
    mock_vision.side_effect = ["version one text", "completely different version"]
    result = ingest_photo(str(img), "test-subject", UID)
    assert result["status"] == "needs_review"
    assert result["confidence"] < 0.75
    pending = [p for p in list_pending(UID, "test-subject") if p["source"] == "photo:note.png"]
    assert len(pending) >= 1


@patch("ingest.photo_ocr_ingest._vision_call")
def test_high_confidence_returns_chunk(mock_vision, tmp_path):
    img = tmp_path / "good.png"
    img.write_bytes(b"fake")
    text = "Linear regression uses y = mx + b"
    mock_vision.side_effect = [text, text]
    result = ingest_photo(str(img), "test-subject", UID)
    assert result["status"] == "ok"
    assert result["chunk"]["content"] == text
