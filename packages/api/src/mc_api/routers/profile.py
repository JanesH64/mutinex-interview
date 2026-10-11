import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response

from mc_api.dependencies import get_current_user, get_scope, require_roles
from mc_api.models import AppUser, CrewSkill, Skill, Unavailability
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
) -> Response:
    crew_skill = scope.session.scalar(
        scope.select(CrewSkill).where(CrewSkill.user_id == user.id, CrewSkill.skill_id == skill_id)
    )
    if crew_skill is None:
        logger.info("skill remove by user %s rejected: skill %s not in profile", user.id, skill_id)
        raise HTTPException(404, "Not found")
    scope.session.delete(crew_skill)
    scope.session.commit()
    logger.info("user %s removed skill %s", user.id, skill_id)
    return Response(status_code=204)


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
