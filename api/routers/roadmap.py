"""Roadmap and concept graph routes."""

from __future__ import annotations

from fastapi import APIRouter

from api.deps import resolve_subject
from api.schemas import CrossCategoryRequest, JobCreatedResponse
from auth.deps import CurrentUser, user_id_from
from core.jobs import create_job, run_in_background
from memory.cross_subject import categories_with_concepts, cross_category_reflect
from memory.graph import fetch_prerequisite_graph, graph_stats, render_graph_html
from memory.roadmap import diff_curriculum, roadmap_narrative

router = APIRouter(tags=["roadmap"])


@router.get("/roadmap/{subject}/diff")
def roadmap_diff(subject: str, user: CurrentUser):
    return diff_curriculum(user_id_from(user), resolve_subject(subject))


@router.post("/roadmap/{subject}/narrative")
def roadmap_narrative_route(subject: str, user: CurrentUser):
    subj = resolve_subject(subject)
    return {"markdown": roadmap_narrative(user_id_from(user), subj)}


@router.post("/roadmap/{subject}/narrative/async", response_model=JobCreatedResponse)
def roadmap_narrative_async(subject: str, user: CurrentUser):
    subj = resolve_subject(subject)
    uid = user_id_from(user)
    job_id = create_job(uid, "roadmap_narrative", {"subject": subj})
    run_in_background(job_id, lambda: {"markdown": roadmap_narrative(uid, subj)})
    return JobCreatedResponse(job_id=job_id)


@router.post("/graph/{subject}/prerequisites")
def graph_prerequisites(subject: str, user: CurrentUser):
    subj = resolve_subject(subject)
    uid = user_id_from(user)
    graph = fetch_prerequisite_graph(uid, subj)
    return {
        "graph": graph,
        "stats": graph_stats(graph),
        "html": render_graph_html(graph),
    }


@router.post("/graph/{subject}/prerequisites/async", response_model=JobCreatedResponse)
def graph_prerequisites_async(subject: str, user: CurrentUser):
    subj = resolve_subject(subject)
    uid = user_id_from(user)
    job_id = create_job(uid, "graph_prerequisites", {"subject": subj})

    def _run():
        graph = fetch_prerequisite_graph(uid, subj)
        return {
            "graph": graph,
            "stats": graph_stats(graph),
            "html": render_graph_html(graph),
        }

    run_in_background(job_id, _run)
    return JobCreatedResponse(job_id=job_id)


@router.get("/concepts/by-category")
def concepts_by_category(user: CurrentUser, subject: str | None = None):
    return categories_with_concepts(user_id_from(user), resolve_subject(subject))


@router.post("/reflect/cross-category")
def reflect_cross_category(body: CrossCategoryRequest, user: CurrentUser, subject: str | None = None):
    subj = resolve_subject(subject)
    uid = user_id_from(user)
    text = cross_category_reflect(
        body.category_a,
        body.concept_a,
        body.category_b,
        body.concept_b,
        uid,
        subj,
    )
    return {"markdown": text}
