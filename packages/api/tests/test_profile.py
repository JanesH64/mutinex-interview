import pytest

from mc_api.models import Organization
from mc_shared import UserRole

RULE = "Only crew members manage a profile"


def test_crew_shows_own_profile(client, make_user, session, auth):
    crew = make_user(UserRole.CREW)
    org = session.get(Organization, crew.org_id)
    response = client.get("/profile", headers=auth(crew))
    assert response.status_code == 200
    assert response.json() == {
        "username": crew.username,
        "display_name": crew.display_name,
        "org_name": org.name,
    }


@pytest.mark.parametrize("role", [UserRole.DIRECTOR, UserRole.LEAD])
def test_director_and_lead_get_403(client, make_user, role, auth):
    user = make_user(role)
    response = client.get("/profile", headers=auth(user))
    assert response.status_code == 403
    assert response.json() == {"role": role, "rule": RULE}


def test_profile_without_token_is_401(client):
    assert client.get("/profile").status_code == 401
