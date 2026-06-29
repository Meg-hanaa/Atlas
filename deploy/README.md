# Small VM deployment

1. Copy `.env.example` → `.env` and fill in secrets.
2. Generate auth secret: `openssl rand -hex 32` → set `ATLAS_AUTH_SECRET`.
3. Set `ATLAS_DOMAIN=your.domain.com` and point DNS A-record to the VM.
4. Set `ATLAS_PUBLIC_URL=https://your.domain.com` and add it to `ATLAS_CORS_ORIGINS`.
5. Build and start:

```bash
docker compose up -d --build
```

6. Open **https://your.domain.com** — register on first visit.
7. Auth tokens (verify / reset) print to `docker compose logs api` when `ATLAS_EMAIL_BACKEND=console`.

## Architecture behind Caddy

| Path | Service |
|------|---------|
| `/` | Streamlit UI (:8501) |
| `/api/*` | FastAPI (:8000, prefix stripped) |

Streamlit talks to the API internally at `http://api:8000`. Caddy terminates TLS and exposes a single HTTPS origin.

## Data

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
