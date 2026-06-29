"""Tests for local structured event logging."""

import json

from monitoring.events import EVENTS_LOG, record_event, trace_span


def test_trace_span_writes_event(tmp_path, monkeypatch):
    import monitoring.events as m

    monkeypatch.setattr(m, "EVENTS_LOG", tmp_path / "atlas_events.jsonl")

    with trace_span("test.op", {"foo": "bar"}):
        pass

    row = json.loads(tmp_path.joinpath("atlas_events.jsonl").read_text().strip())
    assert row["operation"] == "test.op"
    assert row["status"] == "ok"
    assert "bar" in row["attributes_json"]


def test_record_event_on_error(tmp_path, monkeypatch):
    import monitoring.events as m

    monkeypatch.setattr(m, "EVENTS_LOG", tmp_path / "err.jsonl")

    record_event("ingest.pdf", {"path": "/x"}, error=True, error_message="bad pdf")
    row = json.loads(tmp_path.joinpath("err.jsonl").read_text().strip())
    assert row["status"] == "error"
    assert row["error_message"] == "bad pdf"
