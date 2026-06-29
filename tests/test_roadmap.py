"""Tests for curriculum gap detection."""

from scheduler.scheduler import seed_concepts, _connect
from memory.roadmap import diff_curriculum, load_curriculum
from tests.conftest import TEST_USER_ID

UID = TEST_USER_ID


def _clean():
    conn = _connect()
    conn.execute("DELETE FROM concepts")
    conn.commit()
    conn.close()


def test_load_curriculum():
    c = load_curriculum("ml-notes")
    assert "topics" in c
    assert len(c["topics"]) >= 10


def test_diff_finds_missing():
    _clean()
    seed_concepts(
        [{"name": "Linear Regression", "category": "Supervised Learning"}],
        UID,
        "ml-notes",
    )
    diff = diff_curriculum(UID, "ml-notes")
    assert diff["coverage_pct"] < 100
    assert any(t["name"] == "Linear Regression" for t in diff["covered"])
    assert len(diff["missing"]) > 0
