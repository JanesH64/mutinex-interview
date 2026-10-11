from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from mc_api.auth import get_current_user
from mc_api.db import get_session
from mc_api.models import AppUser, Organization


class OrgScope:
    """The only way for a route to read tenant data. Each query is limited to one org."""

    def __init__(self, session: Session, org_id: UUID) -> None:
        self.session = session
        self.org_id = org_id

    def org(self) -> Organization:
        return self.session.scalars(
            select(Organization).where(Organization.id == self.org_id)
        ).one()


def get_scope(
    user: Annotated[AppUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> OrgScope:
    return OrgScope(session, user.org_id)
