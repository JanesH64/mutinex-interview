from mc_api.models import (
    AppUser,
    Assignment,
    AssignmentStatus,
    Mission,
    MissionRequirement,
    Skill,
)
from mc_api.scope import OrgScope

ACTIVE = (AssignmentStatus.INVITED, AssignmentStatus.ACCEPTED)


def overlaps(x, mission: Mission):
    """Both end dates count. A model class gives a SQL expression, a row gives a bool."""
    return (x.start_date <= mission.end_date) & (mission.start_date <= x.end_date)


def active_assignments(
    scope: OrgScope, user: AppUser
) -> list[tuple[Assignment, Mission, MissionRequirement, str]]:
    # The row lock makes a profile write or an invite wait for a concurrent write on the same user.
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
            Assignment.status.in_(ACTIVE),
        )
        .order_by(Mission.start_date, MissionRequirement.position)
    )
    return [tuple(r) for r in rows]
