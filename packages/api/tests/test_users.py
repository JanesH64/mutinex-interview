from uuid import uuid4

from mc_api.auth import create_token
from mc_api.models import Organization
from mc_shared import UserRole


def get_user(client, caller, target_id):
    return client.get(
        f"/users/{target_id}", headers={"Authorization": f"Bearer {create_token(caller.id)}"}
    )


def test_director_and_lead_view_own_org_users(client, make_user, session):
    director = make_user(UserRole.DIRECTOR)
    org = session.get(Organization, director.org_id)
    lead = make_user(UserRole.LEAD, org=org)
    crew = make_user(UserRole.CREW, org=org)
    for caller in (director, lead):
        response = get_user(client, caller, crew.id)
        assert response.status_code == 200
        assert response.json() == {
            "id": str(crew.id),
            "username": crew.username,
            "display_name": crew.display_name,
            "role": "CREW",
        }


def test_crew_views_own_profile(client, make_user):
    crew = make_user(UserRole.CREW)
    assert get_user(client, crew, crew.id).status_code == 200


def test_crew_cannot_view_another_user_of_own_org(client, make_user, session):
    lead = make_user(UserRole.LEAD)
    crew = make_user(UserRole.CREW, org=session.get(Organization, lead.org_id))
    response = get_user(client, crew, lead.id)
    assert response.status_code == 403
    assert response.json() == {
        "role": "CREW",
        "rule": "Crew members view only their own profile",
    }


def test_other_org_gives_the_same_404_as_a_missing_id(client, make_user, session):
    director = make_user(UserRole.DIRECTOR)
    org = session.get(Organization, director.org_id)
    lead = make_user(UserRole.LEAD, org=org)
    crew = make_user(UserRole.CREW, org=org)
    other = make_user(UserRole.CREW)
    for caller in (director, lead, crew):
        missing = get_user(client, caller, uuid4())
        response = get_user(client, caller, other.id)
        assert response.status_code == missing.status_code == 404
        assert response.json() == missing.json() == {"detail": "Not found"}


def test_bad_uuid_gives_422(client, make_user):
    crew = make_user(UserRole.CREW)
    assert get_user(client, crew, "not-a-uuid").status_code == 422
