import os
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from mc_api.models import AppUser

# The dev default is at least 32 bytes, so PyJWT does not warn.
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-only-secret-change-me-0123456789")
TOKEN_TTL = timedelta(hours=12)


def unauthorized() -> HTTPException:
    return HTTPException(401, "Not authenticated", headers={"WWW-Authenticate": "Bearer"})


def create_token(user_id: uuid.UUID, now: datetime | None = None) -> str:
    claims = {"sub": str(user_id), "exp": (now or datetime.now(UTC)) + TOKEN_TTL}
    return jwt.encode(claims, JWT_SECRET, algorithm="HS256")


def find_user_by_username(session: Session, username: str) -> AppUser | None:
    # Runs outside OrgScope: the org is not known before login.
    return session.scalar(select(AppUser).where(AppUser.username == username))
