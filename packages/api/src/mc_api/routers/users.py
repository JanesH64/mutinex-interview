from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from mc_api.dependencies import get_current_user, get_scope
from mc_api.errors import Forbidden
from mc_api.models import AppUser
from mc_api.scope import OrgScope
from mc_shared import UserOut, UserRole

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{user_id}")
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
