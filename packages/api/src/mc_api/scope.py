import logging
from typing import TypeVar
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from mc_api.models import Organization

T = TypeVar("T")
logger = logging.getLogger(__name__)


class OrgScope:
    """The only way for a route to read tenant data. Each query is limited to one org."""

    def __init__(self, session: Session, org_id: UUID) -> None:
        self.session = session
        self.org_id = org_id

    def select(self, model: type[T]) -> Select[tuple[T]]:
        return select(model).where(model.org_id == self.org_id)

    def get(self, model: type[T], id: UUID, *, for_update: bool = False) -> T:
        # Not session.get: it has no org filter. A missing row and another org give the same 404.
        query = self.select(model).where(model.id == id)
        row = self.session.scalar(query.with_for_update() if for_update else query)
        if row is None:
            # One message for a missing row and a row of another org, like the 404 body.
            logger.info("not found: %s %s in org %s", model.__name__, id, self.org_id)
            raise HTTPException(404, "Not found")
        return row

    def org(self) -> Organization:
        return self.session.scalars(
            select(Organization).where(Organization.id == self.org_id)
        ).one()
