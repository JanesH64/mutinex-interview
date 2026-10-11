from uuid import uuid4

import pytest
from fastapi import HTTPException

from mc_api.models import AppUser, Organization, Skill
from mc_api.scope import OrgScope
from mc_shared import UserRole


def test_get_hides_other_orgs(session, make_user):
    a_lead = make_user(UserRole.LEAD)
    a_crew = make_user(UserRole.CREW, org=session.get(Organization, a_lead.org_id))
    b_crew = make_user(UserRole.CREW)
    scope = OrgScope(session, a_lead.org_id)
    assert scope.get(AppUser, a_crew.id) is a_crew
    with pytest.raises(HTTPException) as exc:
        scope.get(AppUser, b_crew.id)
    assert exc.value.status_code == 404
    with pytest.raises(HTTPException):
        scope.get(AppUser, uuid4())


def test_select_returns_only_own_org(session, make_user):
    a_lead = make_user(UserRole.LEAD)
    org_a = session.get(Organization, a_lead.org_id)
    a_crew = make_user(UserRole.CREW, org=org_a)
    b_crew = make_user(UserRole.CREW)
    scope = OrgScope(session, org_a.id)
    users = session.scalars(scope.select(AppUser)).all()
    assert {u.id for u in users} == {a_lead.id, a_crew.id}
    assert b_crew not in users

    skill_a = Skill(org_id=org_a.id, name=f"s-{uuid4()}")
    skill_b = Skill(org_id=b_crew.org_id, name=f"s-{uuid4()}")
    session.add_all([skill_a, skill_b])
    session.flush()
    skills = session.scalars(scope.select(Skill)).all()
    assert skills == [skill_a]
