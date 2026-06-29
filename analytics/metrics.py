"""Analytics from FSRS review logs and local cascadeflow event log."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from analytics.review_log import retrievability_timeline, review_history
from monitoring.events import EVENTS_LOG
from routing.models import CHEAP_MODEL, STRONG_MODEL
from scheduler.scheduler import list_concepts

CHEAP_KEY = CHEAP_MODEL.split("/")[-1]
STRONG_KEY = STRONG_MODEL.split("/")[-1]


def _load_events() -> list[dict]:
    if not EVENTS_LOG.is_file():
        return []
    rows = []
    for line in EVENTS_LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def cost_analytics(user_id: str | None = None) -> dict:
    """Aggregate cascadeflow costs from atlas_events.jsonl."""
    events = _load_events()
    total = 0.0
    cheap = 0.0
    strong = 0.0
    by_day: dict[str, float] = defaultdict(float)
    cheap_calls = 0
    strong_calls = 0
    cascaded = 0

    for ev in events:
        cost = ev.get("total_cost")
        if cost is None:
            continue
        try:
            cost_f = float(cost)
        except (TypeError, ValueError):
            continue
        if cost_f <= 0:
            continue
        total += cost_f
        day = (ev.get("recorded_at") or "")[:10]
        if day:
            by_day[day] += cost_f
        model = (ev.get("model_used") or "").lower()
        if STRONG_KEY.lower() in model or "gpt-oss" in model:
            strong += cost_f
            strong_calls += 1
        elif CHEAP_KEY.lower() in model or "qwen" in model:
            cheap += cost_f
            cheap_calls += 1
        if ev.get("cascaded"):
            cascaded += 1

    return {
        "total_cost_usd": round(total, 6),
        "cheap_cost_usd": round(cheap, 6),
        "strong_cost_usd": round(strong, 6),
        "cheap_calls": cheap_calls,
        "strong_calls": strong_calls,
        "cascade_count": cascaded,
        "cost_by_day": [{"date": d, "cost_usd": round(c, 6)} for d, c in sorted(by_day.items())],
    }


def dashboard_summary(user_id: str, subject: str | None = None) -> dict:
    concepts = list_concepts(user_id, subject)
    timeline = retrievability_timeline(user_id, subject)
    history = review_history(user_id, subject, limit=200)
    costs = cost_analytics()

    heatmap = [
        {
            "name": c["name"],
            "category": c["category"],
            "recall_strength": c["recall_strength"],
            "last_reviewed": c["last_reviewed"],
        }
        for c in concepts
    ]

    return {
        "concept_count": len(concepts),
        "review_count": len(history),
        "retrievability_timelines": timeline,
        "heatmap": heatmap,
        "costs": costs,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
