# Deployment

## Render (recommended) — Blueprint

[`render.yaml`](../render.yaml) at the repo root defines both services:

| Service | URL | Start command |
|---------|-----|---------------|
| `atlas-api` | https://atlas-api-9v91.onrender.com | `uvicorn api.main:app --host 0.0.0.0 --port $PORT` |
| `atlas-app` | https://atlas-app-shnc.onrender.com | `streamlit run app.py --server.port $PORT ...` |

### One-click deploy

1. Push this repo to GitHub
2. [Render Dashboard](https://dashboard.render.com) → **New** → **Blueprint**
3. Select the repo — Render detects `render.yaml`
4. Paste secrets when prompted (Hindsight, Groq, OpenAI, Google OAuth)
5. Deploy both services

### Google OAuth redirect URIs

Add **both** in [Google Cloud Console](https://console.cloud.google.com/apis/credentials) → your OAuth client → **Authorized redirect URIs**:

- `http://127.0.0.1:8000/auth/google/callback` (local)
- `https://atlas-api-9v91.onrender.com/auth/google/callback` (production)

`redirect_uri_mismatch` means the production URL above is missing or has a typo. The callback goes to the **API** host, not the Streamlit app.

### Auth accounts on Render

SQLite on Render is **ephemeral** — each deploy starts a fresh `auth.db`. Local accounts do **not** carry over. Register again on production (or use Google sign-in after fixing OAuth).

### YouTube ingest on Render

YouTube often **blocks transcript requests from cloud IPs** (Render, AWS, etc.). You may see a 502 with a clear message. Workarounds:

- Use **Ingest demo sources** (pre-configured URLs)
- Ingest YouTube **locally** (`uvicorn` + `streamlit` on your machine) — data goes to your Hindsight cloud bank and appears on Render too
- Paste LeetCode prompts or PDF text manually

### Sync existing manual services

If you already created `atlas-api` and `atlas-app` by hand, either:

- Delete them and redeploy via Blueprint, or
- **Generate Blueprint** from existing services (Render Dashboard → service → **Connect** → export to `render.yaml`)

Service **names** in `render.yaml` must match (`atlas-api`, `atlas-app`) for Render to adopt them.

---

## Small VM — Docker + Caddy

1. Copy `.env.example` → `.env` and fill in secrets
2. Generate auth secret: `openssl rand -hex 32` → set `ATLAS_AUTH_SECRET`
3. Set `ATLAS_DOMAIN=your.domain.com` and point DNS A-record to the VM
4. Set `ATLAS_PUBLIC_URL=https://your.domain.com` and add it to `ATLAS_CORS_ORIGINS`
5. Build and start:

```bash
docker compose up -d --build
```

### Architecture behind Caddy

| Path | Service |
|------|---------|
| `/` | Streamlit UI (:8501) |
| `/api/*` | FastAPI (:8000, prefix stripped) |

Streamlit talks to the API internally at `http://api:8000`. Caddy terminates TLS and exposes a single HTTPS origin.

### Data

SQLite, Piper voices, FSRS review logs, and event logs persist in Docker volume `atlas_data`.

Backup:

```bash
docker run --rm -v atlas_atlas_data:/data -v $(pwd):/backup alpine tar czf /backup/atlas-data.tgz /data
```

## Local dev (no Docker)

```bash
uvicorn api.main:app --reload
streamlit run app.py
```

Set `ATLAS_AUTH_DISABLED=1` for quick local testing without login.
