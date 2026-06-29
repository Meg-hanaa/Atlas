"""Tests for FSRS scheduler."""

from fsrs import Rating

from scheduler.scheduler import (
    _fsrs,
    grade_to_rating,
    seed_concepts,
    update_after_review,
    list_concepts,
    _connect,
)
from tests.conftest import TEST_USER_ID

UID = TEST_USER_ID


def _clean():
    conn = _connect()
    conn.execute("DELETE FROM concepts")
    conn.commit()
    conn.close()


def test_grade_to_rating_mapping():
    assert grade_to_rating(correct=False, partial=False) == Rating.Again
    assert grade_to_rating(correct=False, partial=True) == Rating.Hard
    assert grade_to_rating(correct=True, partial=False) == Rating.Good
    assert grade_to_rating(correct=True, partial=False, easy=True) == Rating.Easy


def test_fsrs_review_updates_retrievability():
    _clean()
    seed_concepts([{"name": "Gradient Descent", "category": "Optimization"}], UID, "ml-notes")
    concepts = list_concepts(UID, "ml-notes")
    cid = concepts[0]["id"]
    assert concepts[0]["recall_strength"] == 0.0

    update_after_review(cid, UID, correct=True)
    after = list_concepts(UID, "ml-notes")[0]
    assert after["recall_strength"] > 0.9
    assert after["stability"] > 0


def test_fsrs_has_21_parameters():
    assert len(_fsrs.parameters) == 21
