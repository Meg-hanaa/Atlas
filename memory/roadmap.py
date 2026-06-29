"""Learning roadmap: diff curriculum vs retained concepts + reflect() narrative."""

from __future__ import annotations

import json
import os
import re
from difflib import SequenceMatcher

from config import get_subject
from memory.bank import reflect_query
from scheduler.scheduler import list_concepts

CURRICULA_DIR = os.path.join(os.path.dirname(__file__), "..", "curricula")


def load_curriculum(subject: str | None = None) -> dict:
    subj = get_subject(subject)
    # Map subject slug to curriculum file (ml-notes → ml.json)
    slug = subj.replace("-notes", "").replace("_", "-")
    path = os.path.join(CURRICULA_DIR, f"{slug}.json")
    if not os.path.isfile(path):
        path = os.path.join(CURRICULA_DIR, "ml.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _match_score(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def diff_curriculum(user_id: str, subject: str | None = None, match_threshold: float = 0.55) -> dict:
    """Compare curriculum topics to scheduler concepts."""
    curriculum = load_curriculum(subject)
    topics = curriculum.get("topics", [])
    known = list_concepts(user_id, subject)
    known_names = [c["name"] for c in known]

    covered: list[dict] = []
    missing: list[dict] = []
    for topic in topics:
        name = topic["name"]
        best = max((_match_score(name, k) for k in known_names), default=0.0)
        if best >= match_threshold:
            covered.append({**topic, "match_score": round(best, 2)})
        else:
            missing.append(topic)

    extra = []
    topic_names = [t["name"] for t in topics]
    for c in known:
        best = max((_match_score(c["name"], t) for t in topic_names), default=0.0)
        if best < match_threshold:
            extra.append(c)

    return {
        "curriculum_title": curriculum.get("title", ""),
        "covered": covered,
        "missing": missing,
        "extra_in_notes": extra,
        "coverage_pct": round(100 * len(covered) / max(1, len(topics)), 1),
    }


def roadmap_narrative(user_id: str, subject: str | None = None) -> str:
    """reflect() narrates known vs missing and suggested learning order."""
    diff = diff_curriculum(user_id, subject)
    query = f"""\
Based on my study notes and this curriculum gap analysis, write a learning roadmap.

Curriculum: {diff['curriculum_title']}
Coverage: {diff['coverage_pct']}%

Topics I appear to know (matched):
{json.dumps([t['name'] for t in diff['covered']], indent=2)}

Topics missing from my notes:
{json.dumps([t['name'] for t in diff['missing']], indent=2)}

Extra topics in my notes not in curriculum:
{json.dumps([c['name'] for c in diff['extra_in_notes']], indent=2)}

Write:
1. What I've demonstrated understanding of
2. Critical gaps to fill next (prioritized)
3. A suggested learning order for the next 2-4 weeks
Keep it practical for interview prep.
"""
    return reflect_query(user_id, query, subject=subject, budget="high")
