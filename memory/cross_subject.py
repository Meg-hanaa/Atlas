"""Cross-category reflect — category pairs stand in for separate subject banks."""

from __future__ import annotations

from config import get_subject
from memory.bank import reflect_query
from scheduler.scheduler import list_concepts


def categories_with_concepts(user_id: str, subject: str | None = None) -> dict[str, list[dict]]:
    """Group scheduler concepts by category."""
    by_cat: dict[str, list[dict]] = {}
    for c in list_concepts(user_id, subject):
        by_cat.setdefault(c["category"], []).append(c)
    return by_cat


def cross_category_reflect(
    category_a: str,
    concept_a: str,
    category_b: str,
    concept_b: str,
    user_id: str,
    subject: str | None = None,
) -> str:
    """
    Ask reflect() how two concepts from different categories relate.

    Uses one Hindsight bank with two ML categories as a stand-in for true
    cross-bank reflect until a second subject bank is populated.
    """
    subj = get_subject(subject)
    query = f"""\
I am studying {subj}. Compare concepts across two topic areas in my notes.

Category A: {category_a}
Concept A: {concept_a}

Category B: {category_b}
Concept B: {concept_b}

Using only what appears in my retained memories:
1. How does {concept_a} connect to or depend on {concept_b} (and vice versa)?
2. What shared vocabulary, formulas, or mental models link them?
3. If I'm weak in one, how does that affect understanding the other?
4. One concrete study exercise that practices both together.

Be specific to my notes. If the connection is thin, say so honestly.
"""
    return reflect_query(user_id, query, subject=subject, budget="high")


# Alias for roadmap wording — same bank, categories as pseudo-subjects
cross_subject_reflect = cross_category_reflect
