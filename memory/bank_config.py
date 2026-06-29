"""Per-subject Hindsight memory bank configuration (mission, disposition)."""

from __future__ import annotations

DEFAULT_BANK_CONFIG: dict = {
    "name_template": "Atlas — {subject}",
    "mission": (
        "I am a personal learning notebook. I organize study material by concept, "
        "track which sources contributed to each idea, and prioritize deep understanding "
        "over surface-level summaries."
    ),
    "disposition": {"skepticism": 3, "literalism": 3, "empathy": 3},
    "reflect_mission": (
        "When synthesizing notes, favor clear explanations with worked examples and "
        "connections between ideas. Cite all contributing sources."
    ),
}

SUBJECT_BANK_CONFIG: dict[str, dict] = {
    "ml-notes": {
        "mission": (
            "I am an ML study notebook. Prioritize conceptual understanding, intuition, "
            "and worked examples over rote definitions. When consolidating notes, connect "
            "algorithms to when/why they are used, highlight common misconceptions, and "
            "always attribute which source (video, PDF, photo, practice question) each idea came from."
        ),
        "disposition": {"skepticism": 3, "literalism": 2, "empathy": 4},
        "reflect_mission": (
            "Synthesize ML notes for exam and interview prep. Emphasize intuition, "
            "math when it clarifies, and practical examples. Merge duplicate coverage "
            "across sources into one explanation with multi-source attribution."
        ),
    },
    # Add future subjects here, e.g. "sql-notes": {...}
}


def get_bank_config(subject: str) -> dict:
    """Return merged bank config for a subject slug."""
    base = {**DEFAULT_BANK_CONFIG}
    override = SUBJECT_BANK_CONFIG.get(subject, {})
    merged = {**base, **override}
    if "disposition" in override:
        merged["disposition"] = {**base.get("disposition", {}), **override["disposition"]}
    return merged
