"""Seed synthetic review history for live demo of forgetting curve."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from config import get_subject
from memory.bank import extract_concepts_from_notes
from scheduler.scheduler import list_concepts, seed_concepts, set_last_reviewed


def seed_demo_reviews(user_id: str, subject: str | None = None) -> dict:
    subj = get_subject(subject)
    concepts = list_concepts(user_id, subj)
    if not concepts:
        extracted = extract_concepts_from_notes(user_id, subj)
        seed_concepts(extracted, user_id, subj)
        concepts = list_concepts(user_id, subj)

    if not concepts:
        return {"seeded": 0, "message": "No concepts to seed — ingest and reflect first."}

    now = datetime.now(timezone.utc)
    patterns = [
        now - timedelta(days=5),
        now - timedelta(days=2),
        now,
        None,
    ]

    seeded = 0
    for i, concept in enumerate(concepts[:12]):
        pattern = patterns[i % len(patterns)]
        if pattern is None:
            continue
        set_last_reviewed(concept["id"], user_id, pattern.isoformat())
        seeded += 1

    return {
        "seeded": seeded,
        "subject": subj,
        "message": f"SYNTHETIC: backdated {seeded} review records for demo.",
    }


if __name__ == "__main__":
    from auth.deps import TEST_USER

    print(seed_demo_reviews(str(TEST_USER)))
