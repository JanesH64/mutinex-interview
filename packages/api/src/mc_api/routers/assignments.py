from typing import Annotated

from fastapi import APIRouter, Depends

from mc_api.dependencies import get_current_user, get_scope, require_roles
from mc_api.models import AppUser, Assignment, Mission, MissionRequirement, Skill
from mc_api.scope import OrgScope
from mc_shared import AssignmentOut, UserRole

router = APIRouter(
    prefix="/assignments",
    tags=["assignments"],
    dependencies=[
        Depends(
            require_roles(UserRole.CREW, rule="Only crew members view and respond to assignments")
        )
    ],
)


@router.get("")
def list_assignments(
    scope: Annotated[OrgScope, Depends(get_scope)],
    user: Annotated[AppUser, Depends(get_current_user)],
) -> list[AssignmentOut]:
    rows = scope.session.execute(
        scope.select(Assignment)
        .add_columns(Mission, MissionRequirement, Skill.name, AppUser.username)
        .join(
            Mission, (Mission.org_id == Assignment.org_id) & (Mission.id == Assignment.mission_id)
        )
        .join(
            MissionRequirement,
            (MissionRequirement.org_id == Assignment.org_id)
            & (MissionRequirement.id == Assignment.requirement_id),
        )
        .join(
            Skill,
            (Skill.org_id == MissionRequirement.org_id) & (Skill.id == MissionRequirement.skill_id),
        )
        .join(AppUser, (AppUser.org_id == Mission.org_id) & (AppUser.id == Mission.lead_id))
        .where(Assignment.user_id == user.id)
        .order_by(Mission.start_date.desc(), MissionRequirement.position)
    )
    return [
        AssignmentOut(
            id=a.id,
            mission_id=m.id,
            mission_title=m.title,
            mission_status=m.status,
            start_date=m.start_date,
            end_date=m.end_date,
            lead_username=lead,
            position=r.position,
            skill_name=skill,
            min_level=r.min_level,
            status=a.status,
            responded_at=a.responded_at,
        )
        for a, m, r, skill, lead in rows
    ]
