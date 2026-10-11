import logging
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from mc_api.dependencies import get_current_user, get_scope, require_roles
from mc_api.models import AppUser, Assignment, AssignmentStatus, Mission, MissionRequirement, Skill
from mc_api.scope import OrgScope
from mc_api.staffing import active_assignments, overlaps
from mc_shared import AssignmentOut, UserRole

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/assignments",
    tags=["assignments"],
    dependencies=[
        Depends(
            require_roles(UserRole.CREW, rule="Only crew members view and respond to assignments")
        )
    ],
)


def own_assignments(scope: OrgScope, user: AppUser):
    return (
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
    )


def to_out(row) -> AssignmentOut:
    a, m, r, skill, lead = row
    return AssignmentOut(
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


@router.get("")
def list_assignments(
    scope: Annotated[OrgScope, Depends(get_scope)],
    user: Annotated[AppUser, Depends(get_current_user)],
) -> list[AssignmentOut]:
    query = own_assignments(scope, user).order_by(
        Mission.start_date.desc(), MissionRequirement.position
    )
    return [to_out(r) for r in scope.session.execute(query)]


def respond(
    mission_id: UUID, action: Literal["accept", "decline"], scope: OrgScope, user: AppUser
) -> AssignmentOut:
    mission = scope.get(Mission, mission_id)
    # Accept locks the user row first, so a concurrent booking is visible below.
    booked = active_assignments(scope, user) if action == "accept" else []
    own = scope.session.execute(
        own_assignments(scope, user).where(Assignment.mission_id == mission.id)
    ).all()
    if not own:
        logger.info("%s on mission %s: user %s has no assignment", action, mission.id, user.id)
        raise HTTPException(404, "Not found")
    hit = next((r for r in own if r[0].status == AssignmentStatus.INVITED), None)

    def reject(detail: str) -> HTTPException:
        logger.info("%s on mission %s by user %s rejected: %s", action, mission.id, user.id, detail)
        return HTTPException(409, detail)

    if hit is None:
        raise reject("You have no open invite for this mission.")
    for _, other, _, _ in booked:  # ordered by start date
        if other.id != mission.id and overlaps(other, mission):
            raise reject(
                f'You are booked on mission "{other.title}" '
                f"from {other.start_date} to {other.end_date}."
            )
    row = hit[0]
    row.status = AssignmentStatus.ACCEPTED if action == "accept" else AssignmentStatus.DECLINED
    row.responded_at = datetime.now(UTC)
    scope.session.commit()
    logger.info(
        "user %s set assignment %s on mission %s to %s", user.id, row.id, mission.id, row.status
    )
    return to_out(hit)


@router.post("/{mission_id}/accept")
def accept(
    mission_id: UUID,
    scope: Annotated[OrgScope, Depends(get_scope)],
    user: Annotated[AppUser, Depends(get_current_user)],
) -> AssignmentOut:
    return respond(mission_id, "accept", scope, user)


@router.post("/{mission_id}/decline")
def decline(
    mission_id: UUID,
    scope: Annotated[OrgScope, Depends(get_scope)],
    user: Annotated[AppUser, Depends(get_current_user)],
) -> AssignmentOut:
    return respond(mission_id, "decline", scope, user)
