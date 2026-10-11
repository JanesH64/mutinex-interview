import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from mc_api.auth import create_token, find_user_by_username, unauthorized
from mc_api.db import get_session
from mc_api.dependencies import get_current_user, get_scope
from mc_api.models import AppUser
from mc_api.scope import OrgScope
from mc_shared import LoginRequest, Me, Token

router = APIRouter(tags=["auth"])
logger = logging.getLogger(__name__)


@router.post("/auth/login")
def login(body: LoginRequest, session: Annotated[Session, Depends(get_session)]) -> Token:
    user = find_user_by_username(session, body.username)
    if user is None:
        logger.info("login failed: unknown username %r", body.username)
        raise unauthorized()
    logger.info("login ok: user %s role %s org %s", user.id, user.role, user.org_id)
    return Token(access_token=create_token(user.id))


@router.get("/me")
def me(
    user: Annotated[AppUser, Depends(get_current_user)],
    scope: Annotated[OrgScope, Depends(get_scope)],
) -> Me:
    return Me(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        org_id=user.org_id,
        org_name=scope.org().name,
    )
