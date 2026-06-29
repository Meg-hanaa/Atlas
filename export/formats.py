"""Export consolidated notes and flashcards."""

from __future__ import annotations

import io
import os
import re
import tempfile
import zipfile
from pathlib import Path

from memory.bank import consolidated_notes
from scheduler.scheduler import list_concepts


def _slug(name: str) -> str:
    return re.sub(r"[^\w\s-]", "", name).strip().replace(" ", "-").lower() or "concept"


def export_obsidian_markdown(user_id: str, subject: str) -> bytes:
    """Build a zip of markdown files with [[wikilinks]] for Obsidian."""
    notes = consolidated_notes(user_id, subject)
    concepts = list_concepts(user_id, subject)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{subject}/README.md", notes)
        by_cat: dict[str, list] = {}
        for c in concepts:
            by_cat.setdefault(c["category"], []).append(c)
        for cat, items in by_cat.items():
            cat_slug = _slug(cat)
            lines = [f"# {cat}\n"]
            for c in items:
                slug = _slug(c["name"])
                lines.append(f"- [[{slug}]] — recall {c['recall_strength']:.0%}")
            zf.writestr(f"{subject}/{cat_slug}/_index.md", "\n".join(lines))
            for c in items:
                slug = _slug(c["name"])
                related = [f"[[{_slug(x['name'])}]]" for x in items if x["name"] != c["name"]][:5]
                body = f"# {c['name']}\n\nCategory: [[{_slug(cat)}]]\n\nRelated: {', '.join(related)}\n"
                zf.writestr(f"{subject}/{cat_slug}/{slug}.md", body)
    buf.seek(0)
    return buf.read()


def export_anki_deck(user_id: str, subject: str) -> bytes:
    """Generate .apkg from scheduler concepts."""
    import genanki

    concepts = list_concepts(user_id, subject)
    deck_id = abs(hash(f"{user_id}-{subject}")) % (2**63 - 1)
    model_id = deck_id + 1

    model = genanki.Model(
        model_id,
        f"Atlas {subject}",
        fields=[{"name": "Question"}, {"name": "Answer"}],
        templates=[
            {
                "name": "Card",
                "qfmt": "{{Question}}",
                "afmt": "{{FrontSide}}<hr>{{Answer}}",
            }
        ],
    )
    deck = genanki.Deck(deck_id, f"Atlas — {subject}")

    for c in concepts:
        note = genanki.Note(
            model,
            fields=[c["name"], f"Category: {c['category']}\nRecall strength: {c['recall_strength']:.0%}"],
        )
        deck.add_note(note)

    with tempfile.NamedTemporaryFile(suffix=".apkg", delete=False) as tmp:
        path = tmp.name
    try:
        genanki.Package(deck).write_to_file(path)
        return Path(path).read_bytes()
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def export_pdf(user_id: str, subject: str) -> bytes:
    """Render consolidated notes as PDF via weasyprint."""
    import html

    from weasyprint import HTML

    notes = consolidated_notes(user_id, subject)
    safe_notes = html.escape(notes)
    safe_subject = html.escape(subject)
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
body {{ font-family: Georgia, serif; margin: 2cm; line-height: 1.5; }}
h2 {{ color: #333; border-bottom: 1px solid #ccc; }}
h3 {{ color: #555; }}
code {{ background: #f4f4f4; padding: 2px 4px; }}
</style></head><body>
<h1>Atlas Study Guide — {safe_subject}</h1>
<pre style="white-space: pre-wrap; font-family: inherit;">{safe_notes}</pre>
</body></html>"""
    return HTML(string=html).write_pdf()
