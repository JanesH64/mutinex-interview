import logging
import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from mc_api.db import get_session
from mc_api.models import AppUser

# The dev default is at least 32 bytes, so PyJWT does not warn.
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-only-secret-change-me-0123456789")
TOKEN_TTL = timedelta(hours=12)

bearer = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)


def unauthorized() -> HTTPException:
    return HTTPException(401, "Not authenticated", headers={"WWW-Authenticate": "Bearer"})


def create_token(user_id: uuid.UUID, now: datetime | None = None) -> str:
    claims = {"sub": str(user_id), "exp": (now or datetime.now(UTC)) + TOKEN_TTL}
    return jwt.encode(claims, JWT_SECRET, algorithm="HS256")


def find_user_by_username(session: Session, username: str) -> AppUser | None:
    # Runs outside OrgScope: the org is not known before login.
    return session.scalar(select(AppUser).where(AppUser.username == username))


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    session: Annotated[Session, Depends(get_session)],
) -> AppUser:
    if credentials is None:
        logger.info("auth rejected: no bearer token")
        raise unauthorized()
    try:
        claims = jwt.decode(
            credentials.credentials,
            JWT_SECRET,
            algorithms=["HS256"],
            options={"require": ["sub", "exp"]},
        )
        user_id = uuid.UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError) as exc:
        # Log the error class only. Never log the token.
        logger.info("auth rejected: invalid token (%s)", type(exc).__name__)
        raise unauthorized() from None
    # Runs outside OrgScope: the org comes from this row.
    user = session.get(AppUser, user_id)
    if user is None:
        logger.info("auth rejected: user %s does not exist", user_id)
        raise unauthorized()
    return user
