"""Tests for cross-category reflect helpers."""

from scheduler.scheduler import seed_concepts, _connect
from memory.cross_subject import categories_with_concepts
from tests.conftest import TEST_USER_ID

UID = TEST_USER_ID


def _clean():
    conn = _connect()
    conn.execute("DELETE FROM concepts")
    conn.commit()
    conn.close()


def test_categories_with_concepts_groups_by_category():
    _clean()
    seed_concepts(
        [
            {"name": "Linear Regression", "category": "Supervised Learning"},
            {"name": "Gradient Descent", "category": "Optimization"},
            {"name": "Logistic Regression", "category": "Supervised Learning"},
        ],
        UID,
        "ml-notes",
    )
    grouped = categories_with_concepts(UID, "ml-notes")
    assert set(grouped.keys()) == {"Supervised Learning", "Optimization"}
    assert len(grouped["Supervised Learning"]) == 2
