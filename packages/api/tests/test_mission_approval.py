import logging
from uuid import uuid4

import pytest
from test_mission_slots import add_slot, make_skill
from test_missions import CREW_403, make_mission

from mc_api.models import MissionStatus, Organization
from mc_shared import UserRole

NOT_OWN = "Directors and leads submit and withdraw only their own missions"
S = MissionStatus


def set_status(session, mission, status):
    mission.status = status
    session.flush()


def status_of(client, auth, user, mission):
    return client.get(f"/missions/{mission.id}", headers=auth(user)).json()["status"]


@pytest.mark.parametrize("role", [UserRole.LEAD, UserRole.DIRECTOR])
def test_owner_submits_a_draft_mission(client, make_user, session, auth, role):
    owner = make_user(role)
    mission = make_mission(session, owner)
    if role == UserRole.LEAD:
        add_slot(session, mission, 1, make_skill(session, owner.org_id, "S1"))
    response = client.post(f"/missions/{mission.id}/submit", headers=auth(owner))
    assert response.status_code == 200
    assert response.json()["status"] == "APPROVAL_REQUIRED"


def test_owner_withdraws_and_can_edit_again(client, make_user, session, auth):
    lead = make_user(UserRole.LEAD)
    mission = make_mission(session, lead)
    set_status(session, mission, S.APPROVAL_REQUIRED)
    response = client.post(f"/missions/{mission.id}/withdraw", headers=auth(lead))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "DRAFT"
    assert body.get("approved_by_username") is None
    assert body.get("approved_at") is None
    patch = client.patch(f"/missions/{mission.id}", json={"title": "New"}, headers=auth(lead))
    assert patch.status_code == 200


@pytest.mark.parametrize("action", ["submit", "withdraw"])
def test_non_owner_in_the_own_org_gets_403(client, make_user, session, auth, action):
    owner = make_user(UserRole.LEAD)
    org = session.get(Organization, owner.org_id)
    mission = make_mission(session, owner)
    start = S.DRAFT if action == "submit" else S.APPROVAL_REQUIRED
    set_status(session, mission, start)
    for other in (make_user(UserRole.LEAD, org=org), make_user(UserRole.DIRECTOR, org=org)):
        response = client.post(f"/missions/{mission.id}/{action}", headers=auth(other))
        assert response.status_code == 403
        assert response.json() == {"role": other.role.value, "rule": NOT_OWN}
        assert status_of(client, auth, other, mission) == start.value


@pytest.mark.parametrize(
    "action, status",
    [("submit", s) for s in (S.APPROVAL_REQUIRED, S.APPROVED, S.ACTIVE, S.COMPLETED, S.CANCELLED)]
    + [("withdraw", s) for s in (S.DRAFT, S.APPROVED, S.ACTIVE, S.COMPLETED, S.CANCELLED)],
)
def test_wrong_status_gives_409(client, make_user, session, auth, action, status):
    lead = make_user(UserRole.LEAD)
    mission = make_mission(session, lead)
    set_status(session, mission, status)
    response = client.post(f"/missions/{mission.id}/{action}", headers=auth(lead))
    allowed = "DRAFT" if action == "submit" else "APPROVAL_REQUIRED"
    assert response.status_code == 409
    assert response.json() == {
        "detail": f"Mission is {status.value}. {action.capitalize()} is allowed only in {allowed}."
    }
    assert status_of(client, auth, lead, mission) == status.value


def test_non_owner_gets_403_not_409(client, make_user, session, auth):
    owner = make_user(UserRole.LEAD)
    other = make_user(UserRole.LEAD, org=session.get(Organization, owner.org_id))
    mission = make_mission(session, owner)
    set_status(session, mission, S.COMPLETED)
    response = client.post(f"/missions/{mission.id}/submit", headers=auth(other))
    assert response.status_code == 403
    assert response.json() == {"role": "LEAD", "rule": NOT_OWN}


@pytest.mark.parametrize("action", ["submit", "withdraw"])
def test_crew_gets_403(client, make_user, session, auth, action):
    crew = make_user(UserRole.CREW)
    lead = make_user(UserRole.LEAD, org=session.get(Organization, crew.org_id))
    mission = make_mission(session, lead)
    response = client.post(f"/missions/{mission.id}/{action}", headers=auth(crew))
    assert response.status_code == 403
    assert response.json() == CREW_403


@pytest.mark.parametrize("action", ["submit", "withdraw"])
def test_other_org_gives_the_same_404_as_a_missing_id(client, make_user, session, auth, action):
    owner = make_user(UserRole.LEAD)
    mission = make_mission(session, owner)
    start = S.DRAFT if action == "submit" else S.APPROVAL_REQUIRED
    set_status(session, mission, start)
    for caller in (make_user(UserRole.DIRECTOR), make_user(UserRole.LEAD)):
        response = client.post(f"/missions/{mission.id}/{action}", headers=auth(caller))
        missing = client.post(f"/missions/{uuid4()}/{action}", headers=auth(caller))
        assert response.status_code == 404
        assert response.json() == missing.json() == {"detail": "Not found"}
    assert status_of(client, auth, owner, mission) == start.value


def test_details_are_final_in_approval_required(client, make_user, session, auth):
    lead = make_user(UserRole.LEAD)
    mission = make_mission(session, lead)
    skill = make_skill(session, lead.org_id, "S1")
    add_slot(session, mission, 1, skill)
    set_status(session, mission, S.APPROVAL_REQUIRED)
    url = f"/missions/{mission.id}"
    patch = client.patch(url, json={"title": "X"}, headers=auth(lead))
    add = client.post(
        f"{url}/slots", json={"skill_id": str(skill.id), "min_level": 2}, headers=auth(lead)
    )
    remove = client.delete(f"{url}/slots/1", headers=auth(lead))
    for response in (patch, add, remove):
        assert response.status_code == 409


def test_transitions_and_rejections_are_logged(client, make_user, session, auth, caplog):
    lead = make_user(UserRole.LEAD)
    mission = make_mission(session, lead)
    headers = auth(lead)
    token = headers["Authorization"].removeprefix("Bearer ")
    steps = [("submit", 200), ("withdraw", 200), ("withdraw", 409)]
    for action, code in steps:
        caplog.clear()
        with caplog.at_level(logging.INFO):
            response = client.post(f"/missions/{mission.id}/{action}", headers=headers)
        assert response.status_code == code
        records = [r for r in caplog.records if r.name == "mc_api.routers.missions"]
        assert len(records) == 1
        assert str(mission.id) in records[0].getMessage()
        assert all(token not in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize("action", ["submit", "withdraw"])
def test_mission_id_that_is_not_a_uuid_gives_422(client, make_user, auth, action):
    lead = make_user(UserRole.LEAD)
    assert client.post(f"/missions/not-a-uuid/{action}", headers=auth(lead)).status_code == 422
