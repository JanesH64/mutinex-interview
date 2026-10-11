from datetime import date

import pytest
from sqlalchemy import select
from test_mission_slots import add_slot, make_skill
from test_missions import make_mission

from mc_api.models import (
    Assignment,
    AssignmentStatus,
    CrewSkill,
    MissionStatus,
    Organization,
    Unavailability,
)
from mc_shared import UserRole


def assign(session, mission, slot, user, status=AssignmentStatus.INVITED):
    row = Assignment(
        org_id=mission.org_id,
        mission_id=mission.id,
        requirement_id=slot.id,
        user_id=user.id,
        status=status,
    )
    session.add(row)
    session.flush()
    return row


def mission_at(session, lead, title, start, end, status=MissionStatus.APPROVED):
    mission = make_mission(session, lead)
    mission.title, mission.start_date, mission.end_date, mission.status = title, start, end, status
    session.flush()
    return mission


@pytest.fixture
def world(session, make_user):
    """Org A: lead, crew X (Robotics 4, EVA 2), crew Y. Mission M: slot 1 EVA 3, slot 2 Robotics 3."""
    lead = make_user(UserRole.LEAD)
    x = make_user(UserRole.CREW, session.get(Organization, lead.org_id))
    y = make_user(UserRole.CREW, session.get(Organization, lead.org_id))
    robotics = make_skill(session, lead.org_id, "Robotics")
    eva = make_skill(session, lead.org_id, "EVA")
    session.add_all(
        [
            CrewSkill(org_id=x.org_id, user_id=x.id, skill_id=robotics.id, level=4),
            CrewSkill(org_id=x.org_id, user_id=x.id, skill_id=eva.id, level=2),
        ]
    )
    m = mission_at(session, lead, "Orbit Fix", date(2027, 2, 10), date(2027, 2, 20))
    slot1 = add_slot(session, m, 1, eva)
    slot2 = add_slot(session, m, 2, robotics)
    assignment = assign(session, m, slot2, x)
    return {
        "lead": lead, "x": x, "y": y, "robotics": robotics, "eva": eva,
        "m": m, "slot1": slot1, "slot2": slot2, "assignment": assignment,
    }  # fmt: skip


def entry(client, auth, user, start, end):
    body = {"start_date": start, "end_date": end, "reason": "SICK"}
    return client.post("/profile/unavailability", json=body, headers=auth(user))


def skill_line(w, status="INVITED"):
    m = w["m"]
    return (
        f"Conflicts with your {status} assignment on mission 'Orbit Fix' ({m.id}): "
        "slot 2 requires Robotics level 3."
    )


def entry_line(w, status="INVITED"):
    m = w["m"]
    return (
        f"Conflicts with your {status} assignment on mission 'Orbit Fix' ({m.id}): "
        "the mission runs 2027-02-10 to 2027-02-20."
    )


def entries(session, user):
    session.expire_all()
    stmt = select(Unavailability).where(Unavailability.user_id == user.id)
    return sorted((u.start_date, u.end_date) for u in session.scalars(stmt))


def level(session, user, skill):
    session.expire_all()
    return session.scalar(
        select(CrewSkill.level).where(CrewSkill.user_id == user.id, CrewSkill.skill_id == skill.id)
    )


def put(client, auth, w, lvl):
    return client.put(
        f"/profile/skills/{w['robotics'].id}", json={"level": lvl}, headers=auth(w["x"])
    )


def test_entry_touching_the_mission_gives_409_with_the_line(client, session, auth, world):
    response = entry(client, auth, world["x"], "2027-02-20", "2027-02-25")
    assert response.status_code == 409
    assert response.json() == {"detail": entry_line(world)}
    assert entries(session, world["x"]) == []


def test_entry_overlap_edges(client, session, auth, world):
    x = world["x"]
    assert entry(client, auth, x, "2027-02-01", "2027-02-10").status_code == 409
    assert entry(client, auth, x, "2027-02-12", "2027-02-12").status_code == 409
    assert entries(session, x) == []
    assert entry(client, auth, x, "2027-02-21", "2027-02-22").status_code == 201
    assert entry(client, auth, x, "2027-02-01", "2027-02-09").status_code == 201
    assert entries(session, x) == [
        (date(2027, 2, 1), date(2027, 2, 9)),
        (date(2027, 2, 21), date(2027, 2, 22)),
    ]


def test_low_level_gives_409_and_keeps_the_level(client, session, auth, world):
    response = put(client, auth, world, 2)
    assert response.status_code == 409
    assert response.json() == {"detail": skill_line(world)}
    assert level(session, world["x"], world["robotics"]) == 4


def test_level_at_or_above_the_minimum_passes(client, session, auth, world):
    assert put(client, auth, world, 2).status_code == 409
    assert put(client, auth, world, 3).status_code == 200
    assert level(session, world["x"], world["robotics"]) == 3
    assert put(client, auth, world, 5).status_code == 200
    assert level(session, world["x"], world["robotics"]) == 5


def test_remove_gives_409_and_keeps_the_skill(client, session, auth, world):
    response = client.delete(f"/profile/skills/{world['robotics'].id}", headers=auth(world["x"]))
    assert response.status_code == 409
    assert response.json() == {"detail": skill_line(world)}
    assert level(session, world["x"], world["robotics"]) == 4


def test_accepted_assignment_blocks_all_three(client, session, auth, world):
    world["assignment"].status = AssignmentStatus.ACCEPTED
    session.flush()
    x = world["x"]
    response = entry(client, auth, x, "2027-02-12", "2027-02-12")
    assert response.status_code == 409
    assert response.json() == {"detail": entry_line(world, "ACCEPTED")}
    response = put(client, auth, world, 2)
    assert response.status_code == 409
    assert response.json() == {"detail": skill_line(world, "ACCEPTED")}
    response = client.delete(f"/profile/skills/{world['robotics'].id}", headers=auth(x))
    assert response.status_code == 409
    assert response.json() == {"detail": skill_line(world, "ACCEPTED")}
    assert entries(session, x) == []
    assert level(session, x, world["robotics"]) == 4


@pytest.mark.parametrize("status", list(MissionStatus))
def test_any_mission_status_blocks(client, session, auth, world, status):
    world["m"].status = status
    world["assignment"].status = AssignmentStatus.ACCEPTED
    session.flush()
    assert put(client, auth, world, 2).status_code == 409
    assert level(session, world["x"], world["robotics"]) == 4


@pytest.mark.parametrize("status", [AssignmentStatus.DECLINED, AssignmentStatus.CANCELLED])
def test_declined_or_cancelled_assignment_does_not_block(client, session, auth, world, status):
    x = world["x"]
    assert entry(client, auth, x, "2027-02-12", "2027-02-12").status_code == 409
    world["assignment"].status = status
    session.flush()
    assert entry(client, auth, x, "2027-02-12", "2027-02-12").status_code == 201
    assert put(client, auth, world, 1).status_code == 200
    assert level(session, x, world["robotics"]) == 1
    response = client.delete(f"/profile/skills/{world['robotics'].id}", headers=auth(x))
    assert response.status_code == 204
    assert level(session, x, world["robotics"]) is None


def test_conflicts_are_sorted_by_mission_start(client, session, auth, world):
    n = mission_at(session, world["lead"], "Base Camp", date(2027, 1, 5), date(2027, 2, 15))
    slot = add_slot(session, n, 3, world["robotics"], 4)
    assign(session, n, slot, world["x"], AssignmentStatus.ACCEPTED)
    response = put(client, auth, world, 2)
    assert response.status_code == 409
    lines = response.json()["detail"].split("\n")
    assert lines == [
        (
            f"Conflicts with your ACCEPTED assignment on mission 'Base Camp' ({n.id}): "
            "slot 3 requires Robotics level 4."
        ),
        skill_line(world),
    ]
    assert level(session, world["x"], world["robotics"]) == 4


def test_slot_of_another_skill_does_not_block(client, session, auth, world):
    world["assignment"].requirement_id = world["slot1"].id  # now an EVA slot
    session.flush()
    x = world["x"]
    response = client.delete(f"/profile/skills/{world['eva'].id}", headers=auth(x))
    assert response.status_code == 409
    assert "slot 1 requires EVA level 3." in response.json()["detail"]
    assert put(client, auth, world, 1).status_code == 200
    assert level(session, x, world["robotics"]) == 1


def test_assignment_of_another_crew_member_does_not_block(client, session, auth, world):
    assign(session, world["m"], world["slot1"], world["y"])
    x = world["x"]
    assert entry(client, auth, x, "2027-02-12", "2027-02-12").status_code == 409
    world["assignment"].status = AssignmentStatus.DECLINED
    session.flush()
    assert entry(client, auth, x, "2027-02-12", "2027-02-12").status_code == 201
