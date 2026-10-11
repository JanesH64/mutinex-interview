from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import text
from test_mission_slots import add_slot, make_skill
from test_missions import CREW_403, make_mission
from test_profile_conflicts import assign

from mc_api.models import (
    AssignmentStatus,
    CrewSkill,
    MissionRequirement,
    MissionStatus,
    Organization,
    Unavailability,
)
from mc_shared import UnavailabilityReason, UserRole

NOT_OWNER = "Directors and leads run the matcher only on their own missions"
TABLES = [
    "organization", "app_user", "skill", "crew_skill",
    "unavailability", "mission", "mission_requirement", "assignment",
]  # fmt: skip


def give(session, user, skill, level):
    session.add(CrewSkill(org_id=user.org_id, user_id=user.id, skill_id=skill.id, level=level))
    session.flush()


def counts(session):
    return {t: session.scalar(text(f"SELECT count(*) FROM {t}")) for t in TABLES}


def test_lead_gets_the_preview_and_nothing_is_written(client, make_user, session, auth):
    lead = make_user(UserRole.LEAD)
    mission = make_mission(session, lead)
    mission.start_date, mission.end_date = date(2027, 3, 1), date(2027, 3, 10)
    eva = make_skill(session, lead.org_id, "EVA")
    robotics = make_skill(session, lead.org_id, "Robotics")
    add_slot(session, mission, 1, eva, 3)
    add_slot(session, mission, 2, robotics, 3)
    org = session.get(Organization, lead.org_id)
    c1 = make_user(UserRole.CREW, org)
    c2 = make_user(UserRole.CREW, org)
    other_lead = make_user(UserRole.LEAD, org)
    give(session, c1, eva, 3)
    give(session, c2, eva, 2)
    give(session, other_lead, eva, 5)
    give(session, other_lead, robotics, 3)  # the only Robotics holder: slot 2 must stay null
    org_b = make_user(UserRole.CREW)
    give(session, org_b, make_skill(session, org_b.org_id, "EVA"), 5)
    before = counts(session)
    response = client.get(f"/missions/{mission.id}/match", headers=auth(lead))
    assert response.status_code == 200
    body = response.json()
    assert body["mission_id"] == str(mission.id)
    first, second = body["slots"]
    assert first["slot"]["position"] == 1
    assert first["suggestion"] == {
        "user_id": str(c1.id),
        "username": c1.username,
        "display_name": c1.display_name,
        "level": 3,
        "workload_days": 0,
    }
    assert second["suggestion"] is None
    for user in (c2, other_lead, org_b):
        assert str(user.id) not in response.text
    assert counts(session) == before


def test_director_who_leads_gets_200(client, make_user, session, auth):
    director = make_user(UserRole.DIRECTOR)
    mission = make_mission(session, director)
    assert client.get(f"/missions/{mission.id}/match", headers=auth(director)).status_code == 200


def test_non_owner_gets_403(client, make_user, session, auth):
    lead = make_user(UserRole.LEAD)
    mission = make_mission(session, lead)
    org = session.get(Organization, lead.org_id)
    for other in (make_user(UserRole.LEAD, org), make_user(UserRole.DIRECTOR, org)):
        response = client.get(f"/missions/{mission.id}/match", headers=auth(other))
        assert response.status_code == 403
        assert response.json() == {"role": other.role.value, "rule": NOT_OWNER}


@pytest.mark.parametrize("status", [s for s in MissionStatus if s is not MissionStatus.DRAFT])
def test_not_draft_gives_409(client, make_user, session, auth, status):
    lead = make_user(UserRole.LEAD)
    mission = make_mission(session, lead)
    mission.status = status
    session.flush()
    response = client.get(f"/missions/{mission.id}/match", headers=auth(lead))
    assert response.status_code == 409
    assert response.json() == {
        "detail": f"Mission is {status.value}. The matcher preview is allowed only in DRAFT."
    }


def test_crew_gets_403(client, make_user, session, auth):
    lead = make_user(UserRole.LEAD)
    mission = make_mission(session, lead)
    crew = make_user(UserRole.CREW, session.get(Organization, lead.org_id))
    response = client.get(f"/missions/{mission.id}/match", headers=auth(crew))
    assert response.status_code == 403
    assert response.json() == CREW_403


def test_other_org_mission_gives_the_same_404_as_a_random_id(client, make_user, session, auth):
    mission = make_mission(session, make_user(UserRole.LEAD))
    org_a = make_user(UserRole.LEAD).org_id
    for role in (UserRole.DIRECTOR, UserRole.LEAD):
        user = make_user(role, session.get(Organization, org_a))
        response = client.get(f"/missions/{mission.id}/match", headers=auth(user))
        random = client.get(f"/missions/{uuid4()}/match", headers=auth(user))
        assert response.status_code == 404
        assert response.json() == random.json() == {"detail": "Not found"}


def test_archived_slot_is_left_out_and_no_slots_gives_empty(client, make_user, session, auth):
    from datetime import UTC, datetime

    lead = make_user(UserRole.LEAD)
    mission = make_mission(session, lead)
    empty = make_mission(session, lead)
    skill = make_skill(session, lead.org_id, "EVA")
    rows = [add_slot(session, mission, p, skill) for p in (1, 2, 3)]
    rows[1].archived_at = datetime.now(UTC)
    session.flush()
    body = client.get(f"/missions/{mission.id}/match", headers=auth(lead)).json()
    assert [s["slot"]["position"] for s in body["slots"]] == [1, 3]
    body = client.get(f"/missions/{empty.id}/match", headers=auth(lead)).json()
    assert body["slots"] == []


def test_org_without_crew_gives_null_suggestion(client, make_user, session, auth):
    lead = make_user(UserRole.LEAD)
    mission = make_mission(session, lead)
    add_slot(session, mission, 1, make_skill(session, lead.org_id, "EVA"))
    response = client.get(f"/missions/{mission.id}/match", headers=auth(lead))
    assert response.status_code == 200
    assert response.json()["slots"][0]["suggestion"] is None


def test_bad_mission_id_gives_422(client, make_user, auth):
    lead = make_user(UserRole.LEAD)
    assert client.get("/missions/not-a-uuid/match", headers=auth(lead)).status_code == 422


def busy_setup(session, make_user, slots=1):
    """A DRAFT mission 2027-03-01..10 with EVA >= 3 slots and one EVA 3 crew member."""
    lead = make_user(UserRole.LEAD)
    mission = make_mission(session, lead)
    mission.start_date, mission.end_date = date(2027, 3, 1), date(2027, 3, 10)
    eva = make_skill(session, lead.org_id, "EVA")
    for position in range(1, slots + 1):
        add_slot(session, mission, position, eva, 3)
    crew = make_user(UserRole.CREW, session.get(Organization, lead.org_id))
    give(session, crew, eva, 3)
    return lead, mission, eva, crew


def leave(session, user, start, end):
    session.add(
        Unavailability(
            org_id=user.org_id,
            user_id=user.id,
            start_date=start,
            end_date=end,
            reason=UnavailabilityReason.HOLIDAY,
        )
    )
    session.flush()


def suggested(client, auth, lead, mission, slot=0):
    response = client.get(f"/missions/{mission.id}/match", headers=auth(lead))
    assert response.status_code == 200
    return response.json()["slots"][slot]["suggestion"]


@pytest.mark.parametrize(
    ("start", "end", "blocked"),
    [
        (date(2027, 2, 20), date(2027, 3, 1), True),
        (date(2027, 3, 10), date(2027, 3, 12), True),
        (date(2027, 2, 20), date(2027, 2, 28), False),
        (date(2027, 3, 11), date(2027, 3, 12), False),
    ],
)
def test_leave_blocks_only_when_it_overlaps_the_dates(
    client, make_user, session, auth, start, end, blocked
):
    lead, mission, _, crew = busy_setup(session, make_user)
    leave(session, crew, start, end)
    result = suggested(client, auth, lead, mission)
    assert (result is None) if blocked else (result["user_id"] == str(crew.id))


def other_mission_assignment(session, lead, eva, crew, start, end, status):
    other = make_mission(session, lead)
    # INVITED, ACCEPTED and DECLINED rows need an APPROVED mission. CANCELLED rows fit DRAFT.
    if status != AssignmentStatus.CANCELLED:
        other.status = MissionStatus.APPROVED
    other.start_date, other.end_date = start, end
    slot = add_slot(session, other, 1, eva, 3)
    assign(session, other, slot, crew, status)


@pytest.mark.parametrize(
    ("status", "start", "end", "blocked"),
    [
        (AssignmentStatus.ACCEPTED, date(2027, 3, 10), date(2027, 3, 15), True),
        (AssignmentStatus.INVITED, date(2027, 3, 10), date(2027, 3, 15), True),
        (AssignmentStatus.DECLINED, date(2027, 3, 10), date(2027, 3, 15), False),
        (AssignmentStatus.CANCELLED, date(2027, 3, 10), date(2027, 3, 15), False),
        (AssignmentStatus.ACCEPTED, date(2027, 2, 20), date(2027, 2, 28), False),
    ],
)
def test_assignment_on_an_overlapping_mission_blocks_only_when_active(
    client, make_user, session, auth, status, start, end, blocked
):
    lead, mission, eva, crew = busy_setup(session, make_user)
    other_mission_assignment(session, lead, eva, crew, start, end, status)
    result = suggested(client, auth, lead, mission)
    assert (result is None) if blocked else (result["user_id"] == str(crew.id))


def test_declined_on_this_mission_is_never_suggested(client, make_user, session, auth):
    lead, mission, _, crew = busy_setup(session, make_user)
    slot = session.query(MissionRequirement).filter_by(mission_id=mission.id).one()
    assign(session, mission, slot, crew, AssignmentStatus.DECLINED)
    assert suggested(client, auth, lead, mission) is None


def test_busy_crew_is_skipped_and_the_free_one_takes_slot_one(client, make_user, session, auth):
    lead, mission, eva, x = busy_setup(session, make_user, slots=2)
    y = make_user(UserRole.CREW, session.get(Organization, lead.org_id))
    give(session, y, eva, 3)
    leave(session, x, date(2027, 2, 25), date(2027, 3, 2))
    leave(session, x, date(2027, 3, 9), date(2027, 3, 11))
    other_mission_assignment(
        session, lead, eva, x, date(2027, 3, 5), date(2027, 3, 6), AssignmentStatus.ACCEPTED
    )
    response = client.get(f"/missions/{mission.id}/match", headers=auth(lead))
    assert response.status_code == 200
    first, second = response.json()["slots"]
    assert first["suggestion"]["user_id"] == str(y.id)
    assert second["suggestion"] is None
    assert str(x.id) not in response.text


def test_workload_days_counts_active_assignments_in_the_window_ac15(
    client, make_user, session, auth
):
    lead, mission, eva, crew = busy_setup(session, make_user)
    for status, start, end in [
        (AssignmentStatus.ACCEPTED, date(2026, 11, 25), date(2026, 12, 5)),
        (AssignmentStatus.INVITED, date(2027, 6, 1), date(2027, 6, 20)),
        (AssignmentStatus.ACCEPTED, date(2026, 11, 20), date(2026, 11, 30)),
        (AssignmentStatus.DECLINED, date(2027, 4, 1), date(2027, 4, 5)),
    ]:
        other_mission_assignment(session, lead, eva, crew, start, end, status)
    result = suggested(client, auth, lead, mission)
    assert result["user_id"] == str(crew.id)
    assert result["workload_days"] == 13


def test_holders_count_all_crew_and_no_leads_ac13(client, make_user, session, auth):
    lead, mission, eva, eli = busy_setup(session, make_user)
    org = session.get(Organization, lead.org_id)
    robotics = make_skill(session, lead.org_id, "Robotics")
    geology = make_skill(session, lead.org_id, "Geology")
    give(session, eli, robotics, 1)
    for _ in range(2):  # busy Robotics holders still count
        busy = make_user(UserRole.CREW, org)
        give(session, busy, robotics, 1)
        leave(session, busy, date(2027, 3, 5), date(2027, 3, 6))
    zed = make_user(UserRole.CREW, org)
    eli.username, zed.username = "zz-eli", "aa-zed"  # a wrong count then picks zed by name
    give(session, zed, eva, 3)
    give(session, zed, geology, 1)
    give(session, make_user(UserRole.CREW, org), geology, 1)
    for _ in range(2):  # LEADs do not count
        give(session, make_user(UserRole.LEAD, org), geology, 1)
    assert suggested(client, auth, lead, mission)["user_id"] == str(eli.id)
