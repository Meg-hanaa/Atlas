"""Tests for mentor persistence."""

from unittest.mock import patch

from mentor.state import (
    _connect,
    acknowledge_category,
    build_mentor_nudges,
    record_category_activity,
)
from scheduler.scheduler import seed_concepts
from tests.conftest import TEST_USER_ID

UID = TEST_USER_ID


def _clean():
    conn = _connect()
    conn.execute("DELETE FROM mentor_category_state")
    conn.execute("DELETE FROM mentor_nudge_history")
    conn.execute("DELETE FROM concepts")
    conn.commit()
    conn.close()


@patch("mentor.state.reflect_query", return_value="Confuses bias and variance")
@patch("mentor.state.category_last_touched")
def test_mentor_nudge_persists_same_session(mock_touch, _mock_reflect):
    _clean()
    mock_touch.return_value = {"Optimization": 20.0}
    seed_concepts([{"name": "Gradient Descent", "category": "Optimization"}], UID, "ml-notes")

    first = build_mentor_nudges(UID, "ml-notes", session_id="sess-a")
    second = build_mentor_nudges(UID, "ml-notes", session_id="sess-a")

    assert len(first) == 1
    assert len(second) == 1
    assert first[0]["message"] == second[0]["message"]
    _mock_reflect.assert_called_once()


@patch("mentor.state.reflect_query", return_value="Confuses bias and variance")
@patch("mentor.state.category_last_touched")
def test_mentor_compounds_ignored_sessions(mock_touch, _mock_reflect):
    _clean()
    mock_touch.return_value = {"Optimization": 20.0}
    seed_concepts([{"name": "Gradient Descent", "category": "Optimization"}], UID, "ml-notes")

    n1 = build_mentor_nudges(UID, "ml-notes", session_id="sess-1")[0]
    assert n1["ignored_sessions"] == 0

    n2 = build_mentor_nudges(UID, "ml-notes", session_id="sess-2")[0]
    assert n2["ignored_sessions"] == 1
    assert "Still no review" in n2["message"]

    n3 = build_mentor_nudges(UID, "ml-notes", session_id="sess-3")[0]
    assert n3["ignored_sessions"] == 2
    assert "ignored nudges" in n3["message"]


@patch("mentor.state.reflect_query", return_value="Confuses bias and variance")
@patch("mentor.state.category_last_touched")
def test_category_review_resets_ignore_count(mock_touch, _mock_reflect):
    _clean()
    mock_touch.return_value = {"Optimization": 20.0}
    seed_concepts([{"name": "Gradient Descent", "category": "Optimization"}], UID, "ml-notes")

    build_mentor_nudges(UID, "ml-notes", session_id="sess-1")
    build_mentor_nudges(UID, "ml-notes", session_id="sess-2")
    record_category_activity(UID, "Optimization", "ml-notes")

    n = build_mentor_nudges(UID, "ml-notes", session_id="sess-3")[0]
    assert n["ignored_sessions"] == 0


@patch("mentor.state.reflect_query", return_value="Confuses bias and variance")
@patch("mentor.state.category_last_touched")
def test_acknowledge_does_not_reset_ignore(mock_touch, _mock_reflect):
    _clean()
    mock_touch.return_value = {"Optimization": 20.0}
    seed_concepts([{"name": "Gradient Descent", "category": "Optimization"}], UID, "ml-notes")

    build_mentor_nudges(UID, "ml-notes", session_id="sess-1")
    acknowledge_category(UID, "Optimization", "ml-notes")
    n = build_mentor_nudges(UID, "ml-notes", session_id="sess-2")[0]
    assert n["ignored_sessions"] == 1
