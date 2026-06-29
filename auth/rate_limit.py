"""In-memory rate limiter for /auth/* endpoints."""

from __future__ import annotations

import os
import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

MAX_REQUESTS = int(os.getenv("ATLAS_AUTH_RATE_MAX", "10"))
WINDOW_SECONDS = int(os.getenv("ATLAS_AUTH_RATE_WINDOW", "60"))

_buckets: dict[str, list[float]] = defaultdict(list)


class AuthRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith("/auth"):
            return await call_next(request)

        client = request.client.host if request.client else "unknown"
        key = f"{client}:{path}"
        now = time.time()
        window_start = now - WINDOW_SECONDS
        hits = [t for t in _buckets[key] if t > window_start]
        if len(hits) >= MAX_REQUESTS:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many auth requests — try again later."},
            )
        hits.append(now)
        _buckets[key] = hits
        return await call_next(request)
