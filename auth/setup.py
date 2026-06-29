"""Authentication via fastapi-users (JWT)."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin, models
from fastapi_users.authentication import AuthenticationBackend, BearerTransport, JWTStrategy
from fastapi_users.db import SQLAlchemyBaseOAuthAccountTableUUID, SQLAlchemyBaseUserTableUUID, SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, relationship

from auth.email import send_email
from config import DB_PATH, ensure_data_dir

AUTH_DB_PATH = os.path.abspath(os.path.join(os.path.dirname(DB_PATH), "auth.db"))
ensure_data_dir()

_auth_db_url_path = AUTH_DB_PATH.replace("\\", "/")
DATABASE_URL = os.getenv(
    "ATLAS_AUTH_DATABASE_URL",
    f"sqlite+aiosqlite:///{_auth_db_url_path}",
)
AUTH_SECRET = os.getenv("ATLAS_AUTH_SECRET", "change-me-in-production-use-openssl-rand")
JWT_LIFETIME = int(os.getenv("ATLAS_JWT_LIFETIME_SECONDS", "86400"))
AUTH_DISABLED = os.getenv("ATLAS_AUTH_DISABLED", "").lower() in ("1", "true", "yes")
REQUIRE_VERIFIED = os.getenv("ATLAS_REQUIRE_EMAIL_VERIFICATION", "").lower() in ("1", "true", "yes")
APP_PUBLIC_URL = os.getenv("ATLAS_PUBLIC_URL", "http://localhost:8501")


class Base(DeclarativeBase):
    pass


class OAuthAccount(SQLAlchemyBaseOAuthAccountTableUUID, Base):
    pass


class User(SQLAlchemyBaseUserTableUUID, Base):
    oauth_accounts: Mapped[list[OAuthAccount]] = relationship(
        "OAuthAccount", lazy="joined", cascade="all, delete-orphan"
    )


engine = create_async_engine(DATABASE_URL)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def create_auth_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, User, OAuthAccount)


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = AUTH_SECRET
    verification_token_secret = AUTH_SECRET

    async def on_after_register(self, user: User, request: Request | None = None):
        if user.is_verified:
            return
        await self.request_verify(user, request)

    async def on_after_request_verify(self, user: User, token: str, request: Request | None = None):
        send_email(
            user.email,
            "Verify your Atlas account",
            f"Paste this verification token in Atlas:\n\n{token}\n\nOr open: {APP_PUBLIC_URL}?verify={token}",
        )

    async def on_after_forgot_password(self, user: User, token: str, request: Request | None = None):
        send_email(
            user.email,
            "Reset your Atlas password",
            f"Paste this reset token in Atlas:\n\n{token}\n\nOr open: {APP_PUBLIC_URL}?reset={token}",
        )


async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)


bearer_transport = BearerTransport(tokenUrl="/auth/jwt/login")


def get_jwt_strategy() -> JWTStrategy[models.UP, uuid.UUID]:
    return JWTStrategy(secret=AUTH_SECRET, lifetime_seconds=JWT_LIFETIME)


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])

if REQUIRE_VERIFIED:
    current_active_user = fastapi_users.current_user(active=True, verified=True)
else:
    current_active_user = fastapi_users.current_user(active=True)
