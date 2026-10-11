from uuid import uuid4

from mc_api.auth import create_token
from mc_api.models import Organization, Skill
from mc_shared import UserRole


def auth(user):
    return {"Authorization": f"Bearer {create_token(user.id)}"}


def test_each_role_lists_own_org_skills_sorted_by_name(client, make_user, session):
    director = make_user(UserRole.DIRECTOR)
    org = session.get(Organization, director.org_id)
    lead = make_user(UserRole.LEAD, org=org)
    crew = make_user(UserRole.CREW, org=org)
    other_org = Organization(name=f"org-{uuid4()}")
    session.add(other_org)
    session.flush()
    zeta = Skill(org_id=org.id, name="Zeta")
    alpha = Skill(org_id=org.id, name="Alpha", description="x")
    session.add_all([zeta, alpha, Skill(org_id=other_org.id, name="Beta")])
    session.flush()
    expected = [
        {"id": str(alpha.id), "name": "Alpha", "description": "x"},
        {"id": str(zeta.id), "name": "Zeta", "description": None},
    ]
    for caller in (director, lead, crew):
        response = client.get("/skills", headers=auth(caller))
        assert response.status_code == 200
        assert response.json() == expected


def test_skills_without_token_is_401(client):
    assert client.get("/skills").status_code == 401
