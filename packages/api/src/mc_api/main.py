import logging
import os
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from mc_api.auth import create_token, find_user_by_username, get_current_user, unauthorized
from mc_api.db import get_session
from mc_api.errors import Forbidden, forbidden_handler
from mc_api.models import AppUser
from mc_api.scope import OrgScope, get_scope
from mc_shared import Health, LoginRequest, Me, Token, UserOut, UserRole

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Mission Control")
app.add_exception_handler(Forbidden, forbidden_handler)


@app.get("/health")
def health(session: Annotated[Session, Depends(get_session)]) -> Health:
    session.execute(text("SELECT 1"))
    return Health(status="ok", db="ok")


@app.post("/auth/login")
def login(body: LoginRequest, session: Annotated[Session, Depends(get_session)]) -> Token:
    user = find_user_by_username(session, body.username)
    if user is None:
        logger.info("login failed: unknown username %r", body.username)
        raise unauthorized()
    logger.info("login ok: user %s role %s org %s", user.id, user.role, user.org_id)
    return Token(access_token=create_token(user.id))


@app.get("/me")
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


@app.get("/users/{user_id}")
def get_user(
    user_id: UUID,
    user: Annotated[AppUser, Depends(get_current_user)],
    scope: Annotated[OrgScope, Depends(get_scope)],
) -> UserOut:
    # The scope lookup runs first, so another org gives 404 before any role check.
    target = scope.get(AppUser, user_id)
    if user.role == UserRole.CREW and target.id != user.id:
        raise Forbidden(UserRole.CREW, "Crew members view only their own profile")
    return UserOut(
        id=target.id,
        username=target.username,
        display_name=target.display_name,
        role=target.role,
    )
