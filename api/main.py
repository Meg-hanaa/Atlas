"""FastAPI application entrypoint."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

import config  # noqa: F401 — SSL + logging bootstrap

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import (
    analytics,
    assessments,
    concepts,
    export,
    health,
    ingest,
    interview,
    jobs,
    mentor,
    notes,
    review,
    roadmap,
    subjects,
    voice,
)
from auth.deps import dev_user
from auth.google import GOOGLE_OAUTH_ENABLED, google_oauth_client
from auth.google_routes import router as google_oauth_router
from auth.rate_limit import AuthRateLimitMiddleware
from auth.schemas import UserCreate, UserRead
from auth.setup import AUTH_DISABLED, AUTH_SECRET, auth_backend, create_auth_db, current_active_user, fastapi_users

_DEFAULT_CORS = "http://localhost:8501,http://127.0.0.1:8501"
ROOT_PATH = os.getenv("ATLAS_API_ROOT_PATH", "")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_auth_db()
    yield


app = FastAPI(
    title="Atlas API",
    version="1.0.0",
    lifespan=lifespan,
    root_path=ROOT_PATH,
)

if os.getenv("ATLAS_AUTH_DISABLED", "").lower() in ("1", "true", "yes"):
    app.dependency_overrides[current_active_user] = dev_user

app.add_middleware(AuthRateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("ATLAS_CORS_ORIGINS", _DEFAULT_CORS).split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_verify_router(UserRead),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/auth",
    tags=["auth"],
)
if GOOGLE_OAUTH_ENABLED and google_oauth_client is not None:
    app.include_router(google_oauth_router)
app.include_router(health.router)
app.include_router(subjects.router)
app.include_router(ingest.router)
app.include_router(notes.router)
app.include_router(concepts.router)
app.include_router(interview.router)
app.include_router(roadmap.router)
app.include_router(mentor.router)
app.include_router(review.router)
app.include_router(voice.router)
app.include_router(analytics.router)
app.include_router(assessments.router)
app.include_router(export.router)
app.include_router(jobs.router)


@app.get("/")
def root():
    return {
        "service": "atlas-api",
        "docs": "/docs",
        "auth_disabled": AUTH_DISABLED,
        "google_oauth_enabled": GOOGLE_OAUTH_ENABLED,
    }
