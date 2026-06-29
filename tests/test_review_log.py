"""Tests for FSRS review log persistence."""

from datetime import datetime, timezone

from analytics.review_log import persist_review_log, review_history
from scheduler.scheduler import _connect, list_concepts, seed_concepts
from tests.conftest import TEST_USER_ID

UID = TEST_USER_ID
SUBJ = "ml-notes"


def _clean():
    conn = _connect()
    conn.execute("DELETE FROM concepts")
    conn.execute("DELETE FROM fsrs_review_log")
    conn.commit()
    conn.close()


class _FakeLog:
    def __init__(self, rating: int):
        self._rating = rating

    def to_dict(self):
        return {
            "rating": self._rating,
            "review_datetime": datetime.now(timezone.utc).isoformat(),
        }


def test_persist_and_query_review_log():
    _clean()
    seed_concepts([{"name": "Backprop", "category": "Optimization"}], UID, SUBJ)
    cid = list_concepts(UID, SUBJ)[0]["id"]

    persist_review_log(
        user_id=UID,
        subject=SUBJ,
        concept_id=cid,
        concept_name="Backprop",
        review_log=_FakeLog(3),
        retrievability=0.92,
        stability=4.5,
        difficulty=5.1,
        review_source="test",
    )

    rows = review_history(UID, SUBJ)
    assert len(rows) == 1
    assert rows[0]["concept_name"] == "Backprop"
    assert rows[0]["rating"] == 3
    assert rows[0]["retrievability"] == 0.92
