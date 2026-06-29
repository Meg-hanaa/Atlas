"""Google OAuth browser routes (fastapi-users + httpx-oauth)."""

from __future__ import annotations

import json

import jwt
import secrets
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from httpx_oauth.integrations.fastapi import OAuth2AuthorizeCallback
from httpx_oauth.oauth2 import OAuth2Token

from auth.google import (
    google_callback_url,
    google_oauth_client,
    google_post_login_url,
    oauth_cookie_secure,
)
from auth.setup import AUTH_SECRET, User, auth_backend, get_user_manager
from fastapi_users.authentication import Strategy
from fastapi_users.exceptions import UserAlreadyExists
from fastapi_users.jwt import decode_jwt
from fastapi_users.manager import BaseUserManager
from fastapi_users.router.common import ErrorCode
from fastapi_users.router.oauth import (
    CSRF_TOKEN_COOKIE_NAME,
    CSRF_TOKEN_KEY,
    STATE_TOKEN_AUDIENCE,
    generate_csrf_token,
    generate_state_token,
)

router = APIRouter(prefix="/auth/google", tags=["auth"])

if google_oauth_client is not None:
    _oauth2_callback = OAuth2AuthorizeCallback(
        google_oauth_client,
        redirect_url=google_callback_url(),
    )

    @router.get("/start")
    async def google_oauth_start(request: Request) -> RedirectResponse:
        """Browser entrypoint — sets CSRF cookie and redirects to Google."""
        csrf_token = generate_csrf_token()
        state = generate_state_token({CSRF_TOKEN_KEY: csrf_token}, AUTH_SECRET)
        authorization_url = await google_oauth_client.get_authorization_url(
            google_callback_url(),
            state,
            None,
        )
        redirect = RedirectResponse(authorization_url, status_code=status.HTTP_302_FOUND)
        redirect.set_cookie(
            CSRF_TOKEN_COOKIE_NAME,
            csrf_token,
            max_age=3600,
            path="/",
            secure=oauth_cookie_secure(),
            httponly=True,
            samesite="lax",
        )
        return redirect

    @router.get("/callback")
    async def google_oauth_callback(
        request: Request,
        access_token_state: tuple[OAuth2Token, str] = Depends(_oauth2_callback),
        user_manager: BaseUserManager[User, object] = Depends(get_user_manager),
        strategy: Strategy[User, object] = Depends(auth_backend.get_strategy),
    ):
        """Complete Google OAuth and redirect to Streamlit with JWT."""
        token, state = access_token_state

        try:
            state_data = decode_jwt(state, AUTH_SECRET, [STATE_TOKEN_AUDIENCE])
        except jwt.DecodeError:
            raise HTTPException(status_code=400, detail=ErrorCode.ACCESS_TOKEN_DECODE_ERROR) from None
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=400, detail=ErrorCode.ACCESS_TOKEN_ALREADY_EXPIRED) from None

        cookie_csrf = request.cookies.get(CSRF_TOKEN_COOKIE_NAME)
        state_csrf = state_data.get(CSRF_TOKEN_KEY)
        if (
            not cookie_csrf
            or not state_csrf
            or not secrets.compare_digest(cookie_csrf, state_csrf)
        ):
            raise HTTPException(status_code=400, detail=ErrorCode.OAUTH_INVALID_STATE)

        account_id, account_email = await google_oauth_client.get_id_email(token["access_token"])
        if account_email is None:
            raise HTTPException(status_code=400, detail=ErrorCode.OAUTH_NOT_AVAILABLE_EMAIL)

        try:
            user = await user_manager.oauth_callback(
                google_oauth_client.name,
                token["access_token"],
                account_id,
                account_email,
                token.get("expires_at"),
                token.get("refresh_token"),
                request,
                associate_by_email=True,
                is_verified_by_default=True,
            )
        except UserAlreadyExists:
            raise HTTPException(status_code=400, detail=ErrorCode.OAUTH_USER_ALREADY_EXISTS) from None

        if not user.is_active:
            raise HTTPException(status_code=400, detail=ErrorCode.LOGIN_BAD_CREDENTIALS)

        login_response = await auth_backend.login(strategy, user)
        await user_manager.on_after_login(user, request, login_response)

        body = login_response.body
        if isinstance(body, bytes):
            body = body.decode()
        payload = json.loads(body)
        return RedirectResponse(
            google_post_login_url(payload["access_token"]),
            status_code=status.HTTP_302_FOUND,
        )
