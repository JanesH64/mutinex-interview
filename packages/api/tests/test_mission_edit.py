from uuid import uuid4

import pytest
from test_missions import CREW_403, auth, make_mission

from mc_api.models import Mission, MissionStatus, Organization
from mc_shared import UserRole

NOT_OWNER = "Directors and leads edit only their own missions"


def test_patch_changes_only_the_given_fields(client, make_user, session):
    lead = make_user(UserRole.LEAD)
    mission = make_mission(session, lead)
    mission.description = "Keep me"
    session.flush()
    response = client.patch(f"/missions/{mission.id}", json={"title": "New"}, headers=auth(lead))
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "New"
    assert body["description"] == "Keep me"
    assert (body["start_date"], body["end_date"]) == ("2027-01-01", "2027-12-31")


def test_merged_dates_must_be_valid(client, make_user, session):
    lead = make_user(UserRole.LEAD)
    mission = make_mission(session, lead)
    mission.end_date = mission.end_date.replace(month=3, day=10)
    session.flush()
    url = f"/missions/{mission.id}"
    ok = client.patch(url, json={"start_date": "2027-03-05"}, headers=auth(lead))
    assert ok.status_code == 200
    bad = client.patch(url, json={"start_date": "2027-03-11"}, headers=auth(lead))
    assert bad.status_code == 422
    assert client.get(url, headers=auth(lead)).json()["start_date"] == "2027-03-05"


@pytest.mark.parametrize("body", [{}, {"title": None}])
def test_empty_or_null_patch_changes_nothing(client, make_user, session, body):
    lead = make_user(UserRole.LEAD)
    mission = make_mission(session, lead)
    response = client.patch(f"/missions/{mission.id}", json=body, headers=auth(lead))
    assert response.status_code == 200
    assert response.json()["title"] == "M"


def test_empty_title_gives_422(client, make_user, session):
    lead = make_user(UserRole.LEAD)
    mission = make_mission(session, lead)
    response = client.patch(f"/missions/{mission.id}", json={"title": ""}, headers=auth(lead))
    assert response.status_code == 422


def test_non_owner_in_the_own_org_gets_403(client, make_user, session):
    owner = make_user(UserRole.LEAD)
    org = session.get(Organization, owner.org_id)
    mission = make_mission(session, owner)
    for other in (make_user(UserRole.LEAD, org=org), make_user(UserRole.DIRECTOR, org=org)):
        response = client.patch(f"/missions/{mission.id}", json={"title": "X"}, headers=auth(other))
        assert response.status_code == 403
        assert response.json() == {"role": other.role.value, "rule": NOT_OWNER}
    assert session.get(Mission, mission.id).title == "M"


@pytest.mark.parametrize(
    "status",
    [
        MissionStatus.APPROVAL_REQUIRED,
        MissionStatus.APPROVED,
        MissionStatus.ACTIVE,
        MissionStatus.COMPLETED,
        MissionStatus.CANCELLED,
    ],
)
def test_not_draft_gives_409(client, make_user, session, status):
    lead = make_user(UserRole.LEAD)
    mission = make_mission(session, lead)
    mission.status = status
    session.flush()
    response = client.patch(f"/missions/{mission.id}", json={"title": "X"}, headers=auth(lead))
    assert response.status_code == 409
    assert response.json() == {
        "detail": f"Mission is {status.value}. Edits are allowed only in DRAFT."
    }


def test_other_org_gives_404_and_does_not_change(client, make_user, session):
    director = make_user(UserRole.DIRECTOR)
    lead = make_user(UserRole.LEAD, org=session.get(Organization, director.org_id))
    other = make_mission(session, make_user(UserRole.LEAD))
    for caller in (director, lead):
        response = client.patch(f"/missions/{other.id}", json={"title": "X"}, headers=auth(caller))
        assert response.status_code == 404
        assert response.json() == {"detail": "Not found"}
        missing = client.patch(f"/missions/{uuid4()}", json={"title": "X"}, headers=auth(caller))
        assert missing.json() == {"detail": "Not found"}
    session.expire_all()
    assert session.get(Mission, other.id).title == "M"


def test_crew_gets_403(client, make_user, session):
    crew = make_user(UserRole.CREW)
    mission = make_mission(
        session, make_user(UserRole.LEAD, org=session.get(Organization, crew.org_id))
    )
    response = client.patch(f"/missions/{mission.id}", json={"title": "X"}, headers=auth(crew))
    assert response.status_code == 403
    assert response.json() == CREW_403
