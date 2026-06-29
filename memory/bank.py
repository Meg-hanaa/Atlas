"""Hindsight memory bank wrapper: retain, recall, reflect."""

from __future__ import annotations

from datetime import datetime

from config import get_hindsight_client, get_subject
from core.scope import bank_id as scoped_bank_id
from monitoring.tracing import set_span_attributes, trace_span
from .bank_config import get_bank_config
from .dedup import format_retain_context, prepare_chunk_for_retain

CONSOLIDATED_QUERY = """\
Create consolidated study notes for this subject. Organize by category with clear concept headings.

For EACH concept heading, include:
1. A concise explanation synthesized from my notes
2. A "Sources:" line listing which sources contributed (use source tags from context — they may be comma-separated merged sources like sources=youtube:abc,pdf:notes.pdf,photo:img.png)

When multiple sources cover the same concept, list all of them once — do not repeat the same explanation multiple times.

Format as markdown with ## Category sections and ### Concept headings.
"""


def _bank_id(user_id: str, subject: str | None = None) -> str:
    return scoped_bank_id(user_id, subject)


def ensure_bank(user_id: str, subject: str | None = None) -> str:
    """Create memory bank with per-subject mission/disposition if it does not exist."""
    subj = get_subject(subject)
    bank = _bank_id(user_id, subj)
    client = get_hindsight_client()
    cfg = get_bank_config(subj)
    try:
        client.get_bank_config(bank_id=bank)
    except Exception:
        client.create_bank(
            bank_id=bank,
            name=cfg.get("name_template", "Atlas — {subject}").format(subject=subj),
            mission=cfg["mission"],
            disposition=cfg.get("disposition"),
            reflect_mission=cfg.get("reflect_mission"),
        )
    return bank


def retain_chunk(
    user_id: str,
    content: str,
    source: str,
    date: str | None = None,
    subject: str | None = None,
    context: str | None = None,
    merged_sources: list[str] | None = None,
) -> None:
    """Store one ingested chunk in Hindsight with source in context."""
    bank = ensure_bank(user_id, subject)
    client = get_hindsight_client()
    ts = None
    if date:
        try:
            ts = datetime.fromisoformat(date.replace("Z", "+00:00"))
        except ValueError:
            ts = None

    ctx = context or (f"sources={','.join(merged_sources)}" if merged_sources else f"source={source}")
    metadata = {"source": source, "user_id": user_id}
    if merged_sources:
        metadata["sources"] = ",".join(merged_sources)

    with trace_span(
        "hindsight.retain",
        {
            "bank_id": bank,
            "user_id": user_id,
            "source": source,
            "content_length": len(content),
            "dedup_merged": bool(merged_sources),
        },
    ):
        client.retain(
            bank_id=bank,
            content=content,
            context=ctx,
            timestamp=ts,
            metadata=metadata,
            tags=[get_subject(subject)],
        )


def retain_ingested(user_id: str, chunk: dict, max_chars: int = 12000) -> int:
    """Retain a normalized ingest dict with dedup/merge pass. Large content is split."""
    prepared, action = prepare_chunk_for_retain(chunk, user_id=user_id)
    if prepared is None:
        return 0

    if action == "merge":
        sources = prepared.get("merged_sources", [chunk["source"]])
        retain_chunk(
            user_id,
            content=(
                f"[Merged sources covering the same material: {', '.join(sources)}]\n\n"
                f"{prepared['content'][:4000]}"
            ),
            source=prepared["source"],
            date=chunk.get("date"),
            subject=chunk.get("subject"),
            context=format_retain_context(prepared),
            merged_sources=sources,
        )
        return 1

    content = prepared["content"]
    ctx = format_retain_context(prepared)
    if len(content) <= max_chars:
        retain_chunk(
            user_id,
            content=content,
            source=prepared["source"],
            date=chunk.get("date"),
            subject=chunk.get("subject"),
            context=ctx,
            merged_sources=prepared.get("merged_sources"),
        )
        return 1

    count = 0
    for i in range(0, len(content), max_chars):
        part = content[i : i + max_chars]
        retain_chunk(
            user_id,
            content=part,
            source=f"{prepared['source']}#part{i // max_chars + 1}",
            date=chunk.get("date"),
            subject=chunk.get("subject"),
            context=ctx,
            merged_sources=prepared.get("merged_sources"),
        )
        count += 1
    return count


def search_memories(
    user_id: str,
    query: str,
    subject: str | None = None,
    max_results: int = 8,
) -> list[str]:
    """Recall relevant memories for search/chat grounding."""
    bank = _bank_id(user_id, subject)
    client = get_hindsight_client()
    with trace_span("hindsight.recall", {"bank_id": bank, "query_length": len(query)}):
        response = client.recall(bank_id=bank, query=query, budget="mid")
    texts = []
    for item in response.results[:max_results]:
        text = getattr(item, "text", None) or str(item)
        texts.append(text)
    return texts


def consolidated_notes(user_id: str, subject: str | None = None) -> str:
    """Generate categorized notes via reflect() — this IS the summarizer."""
    bank = _bank_id(user_id, subject)
    client = get_hindsight_client()
    with trace_span("hindsight.reflect", {"bank_id": bank, "operation": "consolidated_notes"}):
        response = client.reflect(
            bank_id=bank,
            query=CONSOLIDATED_QUERY,
            budget="high",
            include_facts=True,
        )
    return response.text


def reflect_query(user_id: str, query: str, subject: str | None = None, budget: str = "mid") -> str:
    """General reflect() wrapper for mock interview mistake surfacing."""
    bank = _bank_id(user_id, subject)
    client = get_hindsight_client()
    with trace_span("hindsight.reflect", {"bank_id": bank, "budget": budget, "query_length": len(query)}):
        response = client.reflect(
            bank_id=bank,
            query=query,
            budget=budget,
            include_facts=True,
        )
    return response.text


CONCEPTS_SCHEMA = {
    "type": "object",
    "properties": {
        "concepts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "category": {"type": "string"},
                },
                "required": ["name", "category"],
            },
        }
    },
    "required": ["concepts"],
}


def extract_concepts_from_notes(user_id: str, subject: str | None = None) -> list[dict]:
    """Extract concept list from reflect-generated notes for scheduler seeding."""
    bank = _bank_id(user_id, subject)
    client = get_hindsight_client()
    query = (
        "From the consolidated study notes, list every distinct learnable concept. "
        "Return JSON matching the schema with name and category for each."
    )
    try:
        response = client.reflect(
            bank_id=bank,
            query=query,
            budget="mid",
            response_schema=CONCEPTS_SCHEMA,
        )
        import json

        data = json.loads(response.text)
        return data.get("concepts", [])
    except Exception:
        notes = consolidated_notes(user_id, subject)
        concepts = []
        current_category = "General"
        for line in notes.splitlines():
            if line.startswith("## "):
                current_category = line[3:].strip()
            elif line.startswith("### "):
                concepts.append({"name": line[4:].strip(), "category": current_category})
        return concepts
