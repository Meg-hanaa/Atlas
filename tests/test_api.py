"""FastAPI route smoke tests."""

import os
from unittest.mock import patch

from fastapi.testclient import TestClient

os.environ["ATLAS_AUTH_DISABLED"] = "1"

from api.main import app

client = TestClient(app)


def test_root():
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["service"] == "atlas-api"
    assert "google_oauth_enabled" in body


@patch("api.routers.health.ensure_bank")
def test_health(mock_ensure):
    mock_ensure.return_value = "ml-notes"
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["hindsight_ok"] is True


@patch("api.routers.concepts.list_concepts", return_value=[])
def test_list_concepts(mock_list):
    r = client.get("/concepts", params={"subject": "ml-notes"})
    assert r.status_code == 200
    assert r.json() == []


@patch("api.routers.concepts.categories_with_concepts", return_value={"Optimization": []})
def test_concepts_by_category(mock_by_cat):
    r = client.get("/concepts/by-category", params={"subject": "ml-notes"})
    assert r.status_code == 200
    assert r.json() == {"Optimization": []}


@patch("api.routers.notes.search_memories", return_value=["note one"])
def test_search(mock_search):
    r = client.get("/search", params={"q": "gradient", "subject": "ml-notes"})
    assert r.status_code == 200
    assert r.json()["results"] == ["note one"]


@patch("api.routers.roadmap.diff_curriculum")
def test_roadmap_diff(mock_diff):
    mock_diff.return_value = {"coverage_pct": 42.0, "covered": [], "missing": [], "extra_in_notes": []}
    r = client.get("/roadmap/ml-notes/diff")
    assert r.status_code == 200
    assert r.json()["coverage_pct"] == 42.0


@patch("api.routers.analytics.dashboard_summary")
def test_analytics_dashboard(mock_dash):
    mock_dash.return_value = {"concept_count": 3, "review_count": 0, "costs": {}, "heatmap": []}
    r = client.get("/analytics/ml-notes/dashboard")
    assert r.status_code == 200
    assert r.json()["concept_count"] == 3


@patch("api.routers.jobs.get_job")
def test_job_status(mock_get):
    mock_get.return_value = {
        "id": "abc",
        "status": "completed",
        "job_type": "notes",
        "result": {"markdown": "hi"},
        "created_at": "2026-01-01T00:00:00+00:00",
        "completed_at": "2026-01-01T00:00:01+00:00",
    }
    r = client.get("/jobs/abc")
    assert r.status_code == 200
    assert r.json()["status"] == "completed"
