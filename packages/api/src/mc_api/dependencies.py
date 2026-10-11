import logging
import uuid
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from mc_api.auth import JWT_SECRET, unauthorized
from mc_api.db import get_session
from mc_api.models import AppUser
from mc_api.scope import OrgScope

bearer = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)


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


def get_scope(
    user: Annotated[AppUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> OrgScope:
    return OrgScope(session, user.org_id)
