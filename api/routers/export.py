"""Export routes — PDF, Obsidian zip, Anki deck."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import Response

from api.deps import resolve_subject
from auth.deps import CurrentUser, user_id_from
from export.formats import export_anki_deck, export_obsidian_markdown, export_pdf

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/{subject}/pdf")
def download_pdf(subject: str, user: CurrentUser):
    subj = resolve_subject(subject)
    data = export_pdf(user_id_from(user), subj)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="atlas-{subj}.pdf"'},
    )


@router.get("/{subject}/obsidian")
def download_obsidian(subject: str, user: CurrentUser):
    subj = resolve_subject(subject)
    data = export_obsidian_markdown(user_id_from(user), subj)
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="atlas-{subj}-obsidian.zip"'},
    )


@router.get("/{subject}/anki")
def download_anki(subject: str, user: CurrentUser):
    subj = resolve_subject(subject)
    data = export_anki_deck(user_id_from(user), subj)
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="atlas-{subj}.apkg"'},
    )
