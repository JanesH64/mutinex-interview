from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

import mc_shared
from mc_api import models
from mc_api.models import Mission, MissionRequirement, MissionStatus, Organization, Skill
from mc_shared import UserRole

BODY = {"title": "T", "start_date": "2027-03-01", "end_date": "2027-03-10"}
CREW_403 = {"role": "CREW", "rule": "Only directors and leads manage and view missions"}


def make_mission(session, lead, start=date(2027, 1, 1)):
    mission = Mission(
        org_id=lead.org_id,
        title="M",
        lead_id=lead.id,
        status=MissionStatus.DRAFT,
        start_date=start,
        end_date=date(2027, 12, 31),
    )
    session.add(mission)
    session.flush()
    return mission


def test_lead_creates_a_draft_mission(client, make_user, auth):
    lead = make_user(UserRole.LEAD)
    response = client.post("/missions", json=BODY, headers=auth(lead))
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "DRAFT"
    assert body["lead_id"] == str(lead.id)
    assert body["lead_username"] == lead.username
    assert body["requires_additional_director"] is False
    assert body["slots"] == []
    assert body["description"] is None


def test_director_mission_requires_additional_director(client, make_user, auth):
    director = make_user(UserRole.DIRECTOR)
    response = client.post("/missions", json=BODY, headers=auth(director))
    assert response.status_code == 201
    assert response.json()["requires_additional_director"] is True


def test_flag_follows_the_current_role_of_the_lead(client, make_user, session, auth):
    lead = make_user(UserRole.LEAD)
    mission_id = client.post("/missions", json=BODY, headers=auth(lead)).json()["id"]
    lead.role = UserRole.DIRECTOR
    session.flush()
    response = client.get(f"/missions/{mission_id}", headers=auth(lead))
    assert response.json()["requires_additional_director"] is True


@pytest.mark.parametrize(
    "body",
    [
        {**BODY, "start_date": "2027-03-10", "end_date": "2027-03-09"},
        {**BODY, "title": ""},
        {k: v for k, v in BODY.items() if k != "title"},
    ],
)
def test_invalid_body_gives_422(client, make_user, body, auth):
    lead = make_user(UserRole.LEAD)
    assert client.post("/missions", json=body, headers=auth(lead)).status_code == 422


def test_list_returns_own_org_missions_newest_start_first(client, make_user, session, auth):
    lead = make_user(UserRole.LEAD)
    older = make_mission(session, lead, date(2027, 1, 1))
    newer = make_mission(session, lead, date(2027, 2, 1))
    make_mission(session, make_user(UserRole.LEAD), date(2027, 3, 1))
    director = make_user(UserRole.DIRECTOR, org=session.get(Organization, lead.org_id))
    directed = make_mission(session, director, date(2027, 1, 15))
    response = client.get("/missions", headers=auth(lead))
    assert response.status_code == 200
    body = response.json()
    assert [m["id"] for m in body] == [str(newer.id), str(directed.id), str(older.id)]
    assert [m["requires_additional_director"] for m in body] == [False, True, False]
    assert set(body[0]) == {
        "id",
        "title",
        "status",
        "start_date",
        "end_date",
        "lead_username",
        "requires_additional_director",
    }


def test_show_returns_active_slots_in_position_order(client, make_user, session, auth):
    lead = make_user(UserRole.LEAD)
    mission = make_mission(session, lead)
    geology = Skill(org_id=lead.org_id, name="Geology")
    eva = Skill(org_id=lead.org_id, name="EVA")
    session.add_all([geology, eva])
    session.flush()
    for position, skill, level, archived in (
        (2, geology, 2, None),
        (1, eva, 3, None),
        (3, eva, 1, datetime.now(UTC)),
    ):
        session.add(
            MissionRequirement(
                org_id=lead.org_id,
                mission_id=mission.id,
                position=position,
                skill_id=skill.id,
                min_level=level,
                archived_at=archived,
            )
        )
    session.flush()
    response = client.get(f"/missions/{mission.id}", headers=auth(lead))
    assert response.status_code == 200
    slots = response.json()["slots"]
    assert [(s["position"], s["skill_id"], s["skill_name"], s["min_level"]) for s in slots] == [
        (1, str(eva.id), "EVA", 3),
        (2, str(geology.id), "Geology", 2),
    ]
    assert all("id" in s for s in slots)


def test_crew_gets_403_on_each_mission_route(client, make_user, session, auth):
    crew = make_user(UserRole.CREW)
    own = make_mission(
        session, make_user(UserRole.LEAD, org=session.get(Organization, crew.org_id))
    )
    other = make_mission(session, make_user(UserRole.LEAD))
    calls = [
        client.post("/missions", json=BODY, headers=auth(crew)),
        client.get("/missions", headers=auth(crew)),
        client.get(f"/missions/{own.id}", headers=auth(crew)),
        client.get(f"/missions/{other.id}", headers=auth(crew)),
    ]
    for response in calls:
        assert response.status_code == 403
        assert response.json() == CREW_403


def test_other_org_gives_the_same_404_as_a_missing_id(client, make_user, session, auth):
    director = make_user(UserRole.DIRECTOR)
    lead = make_user(UserRole.LEAD, org=session.get(Organization, director.org_id))
    other = make_mission(session, make_user(UserRole.LEAD))
    for caller in (director, lead):
        missing = client.get(f"/missions/{uuid4()}", headers=auth(caller))
        response = client.get(f"/missions/{other.id}", headers=auth(caller))
        assert response.status_code == missing.status_code == 404
        assert response.json() == missing.json() == {"detail": "Not found"}


def test_mission_id_that_is_not_a_uuid_gives_422(client, make_user, auth):
    lead = make_user(UserRole.LEAD)
    assert client.get("/missions/not-a-uuid", headers=auth(lead)).status_code == 422


def test_mission_status_is_the_shared_enum():
    assert models.MissionStatus is mc_shared.MissionStatus
