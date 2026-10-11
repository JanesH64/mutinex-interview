from typing import Annotated, TypeVar
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from mc_api.auth import get_current_user
from mc_api.db import get_session
from mc_api.models import AppUser, Organization

T = TypeVar("T")


class OrgScope:
    """The only way for a route to read tenant data. Each query is limited to one org."""

    def __init__(self, session: Session, org_id: UUID) -> None:
        self.session = session
        self.org_id = org_id

    def select(self, model: type[T]) -> Select[tuple[T]]:
        return select(model).where(model.org_id == self.org_id)

    def get(self, model: type[T], id: UUID) -> T:
        # Not session.get: it has no org filter. A missing row and another org give the same 404.
        row = self.session.scalar(self.select(model).where(model.id == id))
        if row is None:
            raise HTTPException(404, "Not found")
        return row

    def org(self) -> Organization:
        return self.session.scalars(
            select(Organization).where(Organization.id == self.org_id)
        ).one()


def get_scope(
    user: Annotated[AppUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> OrgScope:
    return OrgScope(session, user.org_id)
