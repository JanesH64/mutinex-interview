from datetime import UTC, date, datetime
from uuid import uuid4

from test_mission_slots import add_slot, make_skill
from test_profile_conflicts import assign, mission_at

from mc_api.models import AssignmentStatus, MissionStatus, Organization
from mc_shared import UserRole

A = AssignmentStatus
RULE = "Only crew members view and respond to assignments"


def test_crew_lists_own_assignments_newest_mission_first(client, session, make_user, auth):
    lead = make_user(UserRole.LEAD)
    org = session.get(Organization, lead.org_id)
    c, other = make_user(UserRole.CREW, org), make_user(UserRole.CREW, org)
    skill = make_skill(session, org.id, "EVA")
    a = mission_at(session, lead, "A", date(2027, 1, 1), date(2027, 1, 5), MissionStatus.COMPLETED)
    b = mission_at(session, lead, "B", date(2027, 5, 1), date(2027, 5, 9))
    m_c = mission_at(session, lead, "C", date(2027, 5, 1), date(2027, 5, 7))
    slot_a = add_slot(session, a, 1, skill, 2)
    slot_b1, slot_b2 = add_slot(session, b, 1, skill, 1), add_slot(session, b, 2, skill, 4)
    slot_c = add_slot(session, m_c, 1, skill, 3)
    declined = assign(session, a, slot_a, c, A.DECLINED)
    declined.responded_at = datetime(2027, 1, 2, 12, tzinfo=UTC)
    invited = assign(session, b, slot_b2, c)
    accepted = assign(session, m_c, slot_c, c, A.ACCEPTED)
    assign(session, b, slot_b1, other)
    other_org = Organization(name=f"org-{uuid4()}")
    session.add(other_org)
    session.flush()
    foreign_lead = make_user(UserRole.LEAD, other_org)
    foreign_crew = make_user(UserRole.CREW, other_org)
    foreign_skill = make_skill(session, other_org.id, "EVA")
    foreign = mission_at(session, foreign_lead, "FOREIGN", date(2027, 6, 1), date(2027, 6, 5))
    foreign_slot = add_slot(session, foreign, 1, foreign_skill, 1)
    assign(session, foreign, foreign_slot, foreign_crew)
    session.flush()

    response = client.get("/assignments", headers=auth(c))

    assert response.status_code == 200
    rows = response.json()
    assert [r["mission_title"] for r in rows] == ["C", "B", "A"]
    assert [r["position"] for r in rows] == [1, 2, 1]
    assert rows[1] == {
        "id": str(invited.id),
        "mission_id": str(b.id),
        "mission_title": "B",
        "mission_status": "APPROVED",
        "start_date": "2027-05-01",
        "end_date": "2027-05-09",
        "lead_username": lead.username,
        "position": 2,
        "skill_name": "EVA",
        "min_level": 4,
        "status": "INVITED",
        "responded_at": None,
    }
    assert rows[0]["id"] == str(accepted.id)
    assert rows[0]["status"] == "ACCEPTED"
    assert rows[2]["id"] == str(declined.id)
    assert rows[2]["status"] == "DECLINED"
    assert rows[2]["mission_status"] == "COMPLETED"
    assert datetime.fromisoformat(rows[2]["responded_at"]) == declined.responded_at


def test_crew_without_assignments_gets_an_empty_list(client, make_user, auth):
    response = client.get("/assignments", headers=auth(make_user(UserRole.CREW)))
    assert response.status_code == 200
    assert response.json() == []


def test_lead_and_director_get_403(client, make_user, auth):
    for role in (UserRole.LEAD, UserRole.DIRECTOR):
        response = client.get("/assignments", headers=auth(make_user(role)))
        assert response.status_code == 403
        assert response.json() == {"role": role, "rule": RULE}


def test_list_without_token_gives_401(client):
    assert client.get("/assignments").status_code == 401
