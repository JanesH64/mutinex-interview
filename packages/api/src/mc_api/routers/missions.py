import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from mc_api.dependencies import get_current_user, get_scope, require_roles
from mc_api.models import AppUser, Mission, MissionRequirement, Skill
from mc_api.scope import OrgScope
from mc_shared import MissionCreate, MissionOut, MissionStatus, MissionSummary, SlotOut, UserRole

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/missions",
    tags=["missions"],
    dependencies=[
        Depends(
            require_roles(
                UserRole.DIRECTOR,
                UserRole.LEAD,
                rule="Only directors and leads manage and view missions",
            )
        )
    ],
)

Scope = Annotated[OrgScope, Depends(get_scope)]


def mission_out(scope: OrgScope, mission: Mission) -> MissionOut:
    lead = scope.get(AppUser, mission.lead_id)
    rows = scope.session.execute(
        scope.select(MissionRequirement)
        .add_columns(Skill.name)
        .join(
            Skill,
            (Skill.org_id == MissionRequirement.org_id) & (Skill.id == MissionRequirement.skill_id),
        )
        .where(
            MissionRequirement.mission_id == mission.id,
            MissionRequirement.archived_at.is_(None),
        )
        .order_by(MissionRequirement.position)
    )
    return MissionOut(
        id=mission.id,
        title=mission.title,
        description=mission.description,
        status=mission.status,
        start_date=mission.start_date,
        end_date=mission.end_date,
        lead_id=lead.id,
        lead_username=lead.username,
        # Derived from the current role of the lead, never stored.
        requires_additional_director=lead.role == UserRole.DIRECTOR,
        slots=[
            SlotOut(
                id=r.id,
                position=r.position,
                skill_id=r.skill_id,
                skill_name=name,
                min_level=r.min_level,
            )
            for r, name in rows
        ],
    )


@router.post("", status_code=201)
def create_mission(
    body: MissionCreate,
    scope: Scope,
    user: Annotated[AppUser, Depends(get_current_user)],
) -> MissionOut:
    mission = Mission(
        org_id=scope.org_id,
        lead_id=user.id,
        status=MissionStatus.DRAFT,
        **body.model_dump(),
    )
    scope.session.add(mission)
    scope.session.commit()
    logger.info("mission %s created by user %s in org %s", mission.id, user.id, scope.org_id)
    return mission_out(scope, mission)


@router.get("")
def list_missions(scope: Scope) -> list[MissionSummary]:
    rows = scope.session.execute(
        scope.select(Mission)
        .add_columns(AppUser.username, AppUser.role)
        .join(AppUser, (AppUser.org_id == Mission.org_id) & (AppUser.id == Mission.lead_id))
        .order_by(Mission.start_date.desc())
    )
    return [
        MissionSummary(
            id=m.id,
            title=m.title,
            status=m.status,
            start_date=m.start_date,
            end_date=m.end_date,
            lead_username=username,
            requires_additional_director=role == UserRole.DIRECTOR,
        )
        for m, username, role in rows
    ]


@router.get("/{mission_id}")
def get_mission(mission_id: UUID, scope: Scope) -> MissionOut:
    return mission_out(scope, scope.get(Mission, mission_id))
