from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import text
from test_mission_slots import add_slot, make_skill
from test_missions import CREW_403, make_mission

from mc_api.models import CrewSkill, MissionStatus, Organization
from mc_shared import UserRole

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
