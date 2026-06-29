"""Background job status and async long-running tasks."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from auth.deps import CurrentUser, user_id_from
from core.jobs import get_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}")
def job_status(job_id: str, user: CurrentUser):
    job = get_job(job_id, user_id_from(user))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job["id"],
        "status": job["status"],
        "job_type": job["job_type"],
        "result": job.get("result"),
        "error": job.get("error"),
        "created_at": job["created_at"],
        "completed_at": job.get("completed_at"),
    }
