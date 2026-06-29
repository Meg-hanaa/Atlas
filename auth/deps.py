"""Auth dependencies for API routes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends

from auth.setup import User, current_active_user

TEST_USER = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def dev_user() -> User:
    user = User()
    user.id = TEST_USER
    user.email = "test@atlas.local"
    user.is_active = True
    user.is_superuser = False
    user.is_verified = True
    return user


CurrentUser = Annotated[User, Depends(current_active_user)]


def user_id_from(user: User) -> str:
    return str(user.id)
