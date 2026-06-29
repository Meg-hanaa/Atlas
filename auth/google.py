"""Google OAuth2 client and helpers (httpx-oauth + fastapi-users)."""

from __future__ import annotations

import os

from httpx_oauth.clients.google import GoogleOAuth2
from urllib.parse import urlencode

from auth.setup import AUTH_SECRET, APP_PUBLIC_URL

GOOGLE_CLIENT_ID = os.getenv("ATLAS_GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("ATLAS_GOOGLE_OAUTH_CLIENT_SECRET", "")
API_PUBLIC_URL = os.getenv("ATLAS_API_PUBLIC_URL", "http://127.0.0.1:8000").rstrip("/")

GOOGLE_OAUTH_ENABLED = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)

google_oauth_client: GoogleOAuth2 | None = None
if GOOGLE_OAUTH_ENABLED:
    google_oauth_client = GoogleOAuth2(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET)


def google_callback_url() -> str:
    explicit = os.getenv("ATLAS_GOOGLE_OAUTH_CALLBACK_URL")
    if explicit:
        return explicit.rstrip("/")
    return f"{API_PUBLIC_URL}/auth/google/callback"


def google_post_login_url(access_token: str) -> str:
    query = urlencode({"oauth_token": access_token})
    return f"{APP_PUBLIC_URL.rstrip('/')}?{query}"


def oauth_cookie_secure() -> bool:
    return API_PUBLIC_URL.startswith("https://")
