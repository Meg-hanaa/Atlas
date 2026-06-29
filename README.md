# Atlas

Personal digital notebook for learning a subject (demo: Machine Learning). Ingests notes from YouTube, PDFs, handwritten photos, and LeetCode prompts; consolidates them via **Hindsight** `reflect()`; supports search/chat, **FSRS v6** spaced repetition, analytics, skill assessments, and exports.

## Architecture

```
Sources → ingest/* → memory/bank.py (retain) → Hindsight memory bank
                                              ↓
                                    reflect() → consolidated notes
                                              ↓
                         recall() grounds chat / search / flashcards
                                              ↓
              cascadeflow routes cheap (qwen3-32b) → strong (gpt-oss-120b)
                                              ↓
              scheduler/ (FSRS v6 + SQLite) → quiz / mock interview / analytics
                                              ↓
         Streamlit UI ←→ FastAPI API (JWT auth, background jobs)
```

| Component | Role |
|-----------|------|
| **Hindsight** | `retain()` every chunk; `reflect()` for categorized notes; `recall()` for search/chat |
| **cascadeflow** | Cheap-first routing with quality escalation; costs logged to `data/atlas_events.jsonl` |
| **FSRS v6** | Per-concept scheduling; every review persisted to `fsrs_review_log` for analytics |
| **FastAPI** | REST API with multi-user JWT auth, rate-limited `/auth/*`, async jobs for long reflects |
| **Streamlit** | Frontend: notes, roadmap, graph, flashcards, interview, analytics, assessments, export |

Everything is parameterized by `ATLAS_SUBJECT` (default `ml-notes`).

## Quick start (local)

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in HINDSIGHT + GROQ keys
```

Terminal 1 — API:

```bash
uvicorn api.main:app --reload
```

Terminal 2 — UI:

```bash
streamlit run app.py
```

For local dev without login: `ATLAS_AUTH_DISABLED=1`.

## Auth

- Register / log in via Streamlit (or `/auth/register`, `/auth/jwt/login` in API docs).
- **Google sign-in** (optional) — set `ATLAS_GOOGLE_OAUTH_CLIENT_ID` and `ATLAS_GOOGLE_OAUTH_CLIENT_SECRET` from [Google Cloud Console](https://console.cloud.google.com/apis/credentials). Email/password login remains available. If a Google account matches an existing email/password user, accounts are linked automatically (`associate_by_email`).
- Email verification and password reset via **fastapi-users**; tokens print to the API console when `ATLAS_EMAIL_BACKEND=console`.
- Set `ATLAS_REQUIRE_EMAIL_VERIFICATION=1` to block login until verified (email/password users only; Google users are verified by default).
- `/auth/*` endpoints are rate-limited (default 10 requests/minute per IP).

## Docker + HTTPS (VM)

See [deploy/README.md](deploy/README.md). Caddy terminates TLS and proxies:

- `/` → Streamlit
- `/api/*` → FastAPI

```bash
docker compose up -d --build
```

## Render (Blueprint)

A [`render.yaml`](render.yaml) deploys both services in one step:

1. [Render Dashboard](https://dashboard.render.com) → **New** → **Blueprint**
2. Connect this repo — Render reads `render.yaml`
3. Enter secret env vars when prompted (`sync: false` keys)
4. Open **https://atlas-app-shnc.onrender.com** (Streamlit) and **https://atlas-api-9v91.onrender.com/docs** (API)

Production URLs are set in `render.yaml`. Add both OAuth redirect URIs in Google Console (local + Render).

## Features

### Analytics dashboard
FSRS retrievability timelines, cascadeflow cost by day, cheap vs strong model split, recall heatmap.

### Skill assessments
5–10 question category exams generated and graded on the **strong model only**.

### Exports
- **PDF** — consolidated notes via weasyprint
- **Obsidian** — zip of markdown files with `[[wikilinks]]`
- **Anki** — `.apkg` deck via genanki

### Background jobs
Long-running reflect operations (notes, roadmap narrative, concept graph) run in background threads; Streamlit polls `/jobs/{id}`.

## FSRS scheduler

Uses the official **FSRS v6** algorithm (`fsrs` package). Each review writes a `ReviewLog` row to SQLite (`fsrs_review_log`) with rating, retrievability, stability, and difficulty for analytics.

## API overview

| Area | Endpoints |
|------|-----------|
| Auth | `/auth/register`, `/auth/jwt/login`, `/auth/google/start`, `/auth/verify`, `/auth/forgot-password`, `/auth/reset-password` |
| Notes | `/notes/{subject}`, `/notes/{subject}/async` |
| Roadmap | `/roadmap/{subject}/diff`, `/roadmap/{subject}/narrative/async` |
| Graph | `/graph/{subject}/prerequisites/async` |
| Analytics | `/analytics/{subject}/dashboard` |
| Assessments | `/assessments/{subject}/generate`, `/assessments/{subject}/grade` |
| Export | `/export/{subject}/pdf`, `/obsidian`, `/anki` |
| Jobs | `/jobs/{job_id}` |

Full interactive docs at `http://127.0.0.1:8000/docs`.

## Project layout

```
atlas/
├── api/              # FastAPI app + routers
├── auth/             # fastapi-users JWT, email, rate limiting
├── analytics/        # FSRS review log + cost metrics
├── assessments/      # Skill exams (strong model)
├── export/           # PDF, Obsidian, Anki
├── ingest/           # youtube, pdf, photo OCR, leetcode
├── memory/           # Hindsight wrapper, graph, roadmap
├── scheduler/        # FSRS v6 + SQLite concepts
├── core/             # DB, jobs, user scoping
├── app.py            # Streamlit frontend
└── docker-compose.yml
```

## Tests

```bash
ATLAS_AUTH_DISABLED=1 pytest
```

## Operational events

Ingestion and cascadeflow calls log to `data/atlas_events.jsonl`:

```bash
python -c "import json; [print(json.loads(l)['operation'], json.loads(l).get('total_cost')) for l in open('data/atlas_events.jsonl')]"
```
