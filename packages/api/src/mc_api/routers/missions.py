import logging
from datetime import UTC, date, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from mc_api.dependencies import get_current_user, get_scope, require_roles
from mc_api.errors import Forbidden
from mc_api.matcher import WORKLOAD_WINDOW_DAYS, Candidate, assign, workload_days
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
    CrewSuggestion,
    MatchPreview,
    MissionCreate,
    MissionOut,
    MissionStatus,
    MissionSummary,
    MissionUpdate,
    SlotCreate,
    SlotMatch,
    SlotOut,
    UserRole,
)

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


def editable_mission(scope: OrgScope, user: AppUser, mission_id: UUID) -> Mission:
    """Lock the mission of the lead. 404, then 403 for a non-owner, then 409 if not DRAFT."""
    mission = scope.get(Mission, mission_id, for_update=True)
    if mission.lead_id != user.id:
        raise Forbidden(user.role, "Directors and leads edit only their own missions")
    if mission.status != MissionStatus.DRAFT:
        logger.info("edit of mission %s rejected: status %s", mission.id, mission.status)
        raise HTTPException(409, f"Mission is {mission.status}. Edits are allowed only in DRAFT.")
    return mission


@router.patch("/{mission_id}")
def update_mission(
    mission_id: UUID,
    body: MissionUpdate,
    scope: Scope,
    user: Annotated[AppUser, Depends(get_current_user)],
) -> MissionOut:
    mission = editable_mission(scope, user, mission_id)
    changes = body.model_dump(exclude_none=True)
    start = changes.get("start_date", mission.start_date)
    end = changes.get("end_date", mission.end_date)
    if end < start:
        logger.info("edit of mission %s rejected: end before start", mission.id)
        raise HTTPException(422, "end_date must not be before start_date")
    for field, value in changes.items():
        setattr(mission, field, value)
    scope.session.commit()
    logger.info("mission %s edited by user %s: %s", mission.id, user.id, sorted(changes))
    return mission_out(scope, mission)


@router.post("/{mission_id}/slots", status_code=201)
def add_slot(
    mission_id: UUID,
    body: SlotCreate,
    scope: Scope,
    user: Annotated[AppUser, Depends(get_current_user)],
) -> MissionOut:
    mission = editable_mission(scope, user, mission_id)
    if scope.session.scalar(scope.select(Skill).where(Skill.id == body.skill_id)) is None:
        logger.info("slot add to mission %s rejected: unknown skill", mission.id)
        raise HTTPException(422, f"Unknown skill: {body.skill_id}")
    used = set(
        scope.session.scalars(
            scope.select(MissionRequirement)
            .where(
                MissionRequirement.mission_id == mission.id,
                MissionRequirement.archived_at.is_(None),
            )
            .with_only_columns(MissionRequirement.position)
        )
    )
    # The mission row lock serializes this choice.
    position = next(p for p in range(1, len(used) + 2) if p not in used)
    scope.session.add(
        MissionRequirement(
            org_id=scope.org_id,
            mission_id=mission.id,
            position=position,
            skill_id=body.skill_id,
            min_level=body.min_level,
        )
    )
    scope.session.commit()
    logger.info("slot %s added to mission %s by user %s", position, mission.id, user.id)
    return mission_out(scope, mission)


@router.delete("/{mission_id}/slots/{position}")
def remove_slot(
    mission_id: UUID,
    position: int,
    scope: Scope,
    user: Annotated[AppUser, Depends(get_current_user)],
) -> MissionOut:
    mission = editable_mission(scope, user, mission_id)
    slot = scope.session.scalar(
        scope.select(MissionRequirement).where(
            MissionRequirement.mission_id == mission.id,
            MissionRequirement.position == position,
            MissionRequirement.archived_at.is_(None),
        )
    )
    if slot is None:
        logger.info("slot %s removal from mission %s rejected: not found", position, mission.id)
        raise HTTPException(404, "Not found")
    slot.archived_at = datetime.now(UTC)
    scope.session.commit()
    logger.info("slot %s removed from mission %s by user %s", position, mission.id, user.id)
    return mission_out(scope, mission)


@router.get("/{mission_id}/match")
def match_preview(
    mission_id: UUID,
    scope: Scope,
    user: Annotated[AppUser, Depends(get_current_user)],
) -> MatchPreview:
    mission = scope.get(Mission, mission_id)
    if mission.lead_id != user.id:
        raise Forbidden(user.role, "Directors and leads run the matcher only on their own missions")
    if mission.status != MissionStatus.DRAFT:
        logger.info("match preview rejected: mission %s is %s", mission.id, mission.status)
        raise HTTPException(
            409, f"Mission is {mission.status}. The matcher preview is allowed only in DRAFT."
        )
    slots = mission_out(scope, mission).slots
    rows = scope.session.execute(
        scope.select(CrewSkill)
        .add_columns(AppUser)
        .join(AppUser, (AppUser.org_id == CrewSkill.org_id) & (AppUser.id == CrewSkill.user_id))
        .where(AppUser.role == UserRole.CREW)
    ).all()
    users: dict[UUID, AppUser] = {}
    skills: dict[UUID, dict[UUID, int]] = {}
    holders: dict[UUID, int] = {}
    for cs, u in rows:
        users[u.id] = u
        skills.setdefault(u.id, {})[cs.skill_id] = cs.level
        holders[cs.skill_id] = holders.get(cs.skill_id, 0) + 1

    def overlaps(m):
        return (m.start_date <= mission.end_date) & (mission.start_date <= m.end_date)

    busy = set(
        scope.session.scalars(
            scope.select(Unavailability)
            .where(overlaps(Unavailability))
            .with_only_columns(Unavailability.user_id)
        )
    )
    busy |= set(
        scope.session.scalars(
            scope.select(Assignment)
            .where(
                Assignment.mission_id == mission.id,
                Assignment.status == AssignmentStatus.DECLINED,
            )
            .with_only_columns(Assignment.user_id)
        )
    )
    window = timedelta(days=WORKLOAD_WINDOW_DAYS)
    booked: dict[UUID, list[tuple[date, date]]] = {}
    for uid, start, end in scope.session.execute(
        scope.select(Assignment)
        .join(
            Mission, (Mission.org_id == Assignment.org_id) & (Mission.id == Assignment.mission_id)
        )
        .where(
            Assignment.status.in_([AssignmentStatus.INVITED, AssignmentStatus.ACCEPTED]),
            Mission.start_date <= mission.end_date + window,
            Mission.end_date >= mission.start_date - window,
        )
        .with_only_columns(Assignment.user_id, Mission.start_date, Mission.end_date)
    ):
        booked.setdefault(uid, []).append((start, end))
        if start <= mission.end_date and mission.start_date <= end:
            busy.add(uid)
    candidates = [
        Candidate(
            uid,
            users[uid].username,
            sk,
            workload_days(mission.start_date, mission.end_date, booked.get(uid, [])),
        )
        for uid, sk in skills.items()
        if uid not in busy
    ]
    matches = []
    for slot, c in zip(slots, assign(slots, candidates, holders), strict=True):
        suggestion = c and CrewSuggestion(
            user_id=c.user_id,
            username=c.username,
            display_name=users[c.user_id].display_name,
            level=c.skills[slot.skill_id],
            workload_days=c.workload_days,
        )
        matches.append(SlotMatch(slot=slot, suggestion=suggestion))
    return MatchPreview(mission_id=mission.id, slots=matches)
