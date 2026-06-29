"""Analytics dashboard data."""

from __future__ import annotations

from fastapi import APIRouter

from analytics.metrics import dashboard_summary
from api.deps import resolve_subject
from auth.deps import CurrentUser, user_id_from

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/{subject}/dashboard")
def analytics_dashboard(subject: str, user: CurrentUser):
    subj = resolve_subject(subject)
    return dashboard_summary(user_id_from(user), subj)
