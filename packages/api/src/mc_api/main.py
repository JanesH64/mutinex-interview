from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from mc_api.auth import create_token, find_user_by_username, get_current_user
from mc_api.db import get_session
from mc_api.models import AppUser
from mc_api.scope import OrgScope, get_scope
from mc_shared import Health, LoginRequest, Me, Token

app = FastAPI(title="Mission Control")


@app.get("/health")
def health(session: Annotated[Session, Depends(get_session)]) -> Health:
    session.execute(text("SELECT 1"))
    return Health(status="ok", db="ok")


@app.post("/auth/login")
def login(body: LoginRequest, session: Annotated[Session, Depends(get_session)]) -> Token:
    user = find_user_by_username(session, body.username)
    if user is None:
        raise HTTPException(401, "Unknown user", headers={"WWW-Authenticate": "Bearer"})
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
