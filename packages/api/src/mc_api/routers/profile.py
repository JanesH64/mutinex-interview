from typing import Annotated

from fastapi import APIRouter, Depends

from mc_api.dependencies import get_current_user, get_scope, require_roles
from mc_api.models import AppUser
from mc_api.scope import OrgScope
from mc_shared import ProfileOut, UserRole

router = APIRouter(
    prefix="/profile",
    tags=["profile"],
    dependencies=[Depends(require_roles(UserRole.CREW, rule="Only crew members manage a profile"))],
)


@router.get("")
def show_profile(
    user: Annotated[AppUser, Depends(get_current_user)],
    scope: Annotated[OrgScope, Depends(get_scope)],
) -> ProfileOut:
    return ProfileOut(
        username=user.username, display_name=user.display_name, org_name=scope.org().name
    )
