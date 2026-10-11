import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from mc_api.dependencies import get_current_user, get_scope, require_roles
from mc_api.models import (
    AppUser,
    Assignment,
    AssignmentStatus,
    CrewSkill,
    Mission,
    MissionRequirement,
    Skill,
    Unavailability,
)
from mc_api.scope import OrgScope
from mc_shared import (
    CrewSkillOut,
    ProfileOut,
    SkillLevel,
    UnavailabilityCreate,
    UnavailabilityOut,
    UserRole,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/profile",
    tags=["profile"],
    dependencies=[Depends(require_roles(UserRole.CREW, rule="Only crew members manage a profile"))],
)


def active_assignments(
    scope: OrgScope, user: AppUser
) -> list[tuple[Assignment, Mission, MissionRequirement, str]]:
    # The row lock makes a profile write wait for a concurrent write of the same caller.
    scope.get(AppUser, user.id, for_update=True)
    rows = scope.session.execute(
        scope.select(Assignment)
        .add_columns(Mission, MissionRequirement, Skill.name)
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
        .where(
            Assignment.user_id == user.id,
            Assignment.status.in_([AssignmentStatus.INVITED, AssignmentStatus.ACCEPTED]),
        )
        .order_by(Mission.start_date, MissionRequirement.position)
    )
    return [tuple(r) for r in rows]


def reject_conflicts(lines: list[str], action: str) -> None:
    if lines:
        logger.info("%s rejected: %s conflicts", action, len(lines))
        raise HTTPException(409, "\n".join(lines))


def conflict_line(a: Assignment, m: Mission, detail: str) -> str:
    return f"Conflicts with your {a.status} assignment on mission '{m.title}' ({m.id}): {detail}."


@router.get("")
def show_profile(
    user: Annotated[AppUser, Depends(get_current_user)],
    scope: Annotated[OrgScope, Depends(get_scope)],
) -> ProfileOut:
    return ProfileOut(
        username=user.username, display_name=user.display_name, org_name=scope.org().name
    )


@router.get("/skills")
def list_skills(
    user: Annotated[AppUser, Depends(get_current_user)],
    scope: Annotated[OrgScope, Depends(get_scope)],
) -> list[CrewSkillOut]:
    rows = scope.session.execute(
        scope.select(CrewSkill)
        .join(Skill, (Skill.org_id == CrewSkill.org_id) & (Skill.id == CrewSkill.skill_id))
        .where(CrewSkill.user_id == user.id)
        .with_only_columns(CrewSkill.skill_id, Skill.name, CrewSkill.level)
        .order_by(Skill.name)
    )
    return [CrewSkillOut(skill_id=i, skill_name=n, level=lv) for i, n, lv in rows]


@router.put("/skills/{skill_id}")
def set_skill(
    skill_id: UUID,
    body: SkillLevel,
    user: Annotated[AppUser, Depends(get_current_user)],
    scope: Annotated[OrgScope, Depends(get_scope)],
) -> CrewSkillOut:
    skill = scope.session.scalar(scope.select(Skill).where(Skill.id == skill_id))
    if skill is None:
        logger.info("skill set by user %s rejected: unknown skill %s", user.id, skill_id)
        raise HTTPException(422, f"Unknown skill: {skill_id}")
    reject_conflicts(
        [
            conflict_line(a, m, f"slot {r.position} requires {name} level {r.min_level}")
            for a, m, r, name in active_assignments(scope, user)
            if r.skill_id == skill_id and body.level < r.min_level
        ],
        f"skill set by user {user.id} for skill {skill_id}",
    )
    crew_skill = scope.session.scalar(
        scope.select(CrewSkill).where(CrewSkill.user_id == user.id, CrewSkill.skill_id == skill_id)
    )
    if crew_skill is None:
        crew_skill = CrewSkill(org_id=scope.org_id, user_id=user.id, skill_id=skill_id)
        scope.session.add(crew_skill)
    crew_skill.level = body.level
    scope.session.commit()
    logger.info("user %s set skill %s to level %s", user.id, skill_id, body.level)
    return CrewSkillOut(skill_id=skill_id, skill_name=skill.name, level=body.level)


@router.delete("/skills/{skill_id}", status_code=204)
def remove_skill(
    skill_id: UUID,
    user: Annotated[AppUser, Depends(get_current_user)],
    scope: Annotated[OrgScope, Depends(get_scope)],
) -> None:
    crew_skill = scope.session.scalar(
        scope.select(CrewSkill).where(CrewSkill.user_id == user.id, CrewSkill.skill_id == skill_id)
    )
    if crew_skill is None:
        logger.info("skill remove by user %s rejected: skill %s not in profile", user.id, skill_id)
        raise HTTPException(404, "Not found")
    reject_conflicts(
        [
            conflict_line(a, m, f"slot {r.position} requires {name} level {r.min_level}")
            for a, m, r, name in active_assignments(scope, user)
            if r.skill_id == skill_id
        ],
        f"skill remove by user {user.id} for skill {skill_id}",
    )
    scope.session.delete(crew_skill)
    scope.session.commit()
    logger.info("user %s removed skill %s", user.id, skill_id)


@router.get("/unavailability")
def list_unavailability(
    user: Annotated[AppUser, Depends(get_current_user)],
    scope: Annotated[OrgScope, Depends(get_scope)],
) -> list[UnavailabilityOut]:
    rows = scope.session.scalars(
        scope.select(Unavailability)
        .where(Unavailability.user_id == user.id)
        .order_by(Unavailability.start_date, Unavailability.end_date)
    )
    return [UnavailabilityOut.model_validate(r, from_attributes=True) for r in rows]


@router.post("/unavailability", status_code=201)
def add_unavailability(
    body: UnavailabilityCreate,
    user: Annotated[AppUser, Depends(get_current_user)],
    scope: Annotated[OrgScope, Depends(get_scope)],
) -> UnavailabilityOut:
    reject_conflicts(
        [
            conflict_line(a, m, f"the mission runs {m.start_date} to {m.end_date}")
            for a, m, _, _ in active_assignments(scope, user)
            if body.start_date <= m.end_date and body.end_date >= m.start_date
        ],
        f"unavailability add by user {user.id}",
    )
    row = Unavailability(org_id=scope.org_id, user_id=user.id, **body.model_dump())
    scope.session.add(row)
    scope.session.commit()
    logger.info("user %s added unavailability %s", user.id, row.id)
    return UnavailabilityOut.model_validate(row, from_attributes=True)


@router.delete("/unavailability/{unavailability_id}", status_code=204)
def remove_unavailability(
    unavailability_id: UUID,
    user: Annotated[AppUser, Depends(get_current_user)],
    scope: Annotated[OrgScope, Depends(get_scope)],
) -> None:
    row = scope.session.scalar(
        scope.select(Unavailability).where(
            Unavailability.id == unavailability_id, Unavailability.user_id == user.id
        )
    )
    if row is None:
        logger.info(
            "unavailability remove by user %s rejected: %s not found", user.id, unavailability_id
        )
        raise HTTPException(404, "Not found")
    scope.session.delete(row)
    scope.session.commit()
    logger.info("user %s removed unavailability %s", user.id, unavailability_id)
