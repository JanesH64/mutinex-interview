from uuid import uuid4

import pytest
from sqlalchemy import select
from test_missions import CREW_403, make_mission

from mc_api.models import MissionRequirement, MissionStatus, Organization, Skill
from mc_shared import UserRole

NOT_OWNER = "Directors and leads edit only their own missions"


def make_skill(session, org_id, name):
    skill = Skill(org_id=org_id, name=name)
    session.add(skill)
    session.flush()
    return skill


def add_slot(session, mission, position, skill, level=3):
    row = MissionRequirement(
        org_id=mission.org_id,
        mission_id=mission.id,
        position=position,
        skill_id=skill.id,
        min_level=level,
    )
    session.add(row)
    session.flush()
    return row


def rows(session, mission):
    session.expire_all()
    stmt = select(MissionRequirement).where(MissionRequirement.mission_id == mission.id)
    return sorted(
        (r.position, r.skill_id, r.min_level, r.archived_at) for r in session.scalars(stmt)
    )


def test_add_uses_the_lowest_free_position(client, make_user, session, auth):
    lead = make_user(UserRole.LEAD)
    mission = make_mission(session, lead)
    s1 = make_skill(session, lead.org_id, "S1")
    s2 = make_skill(session, lead.org_id, "S2")
    url = f"/missions/{mission.id}/slots"
    first = client.post(url, json={"skill_id": str(s1.id), "min_level": 3}, headers=auth(lead))
    assert first.status_code == 201
    slots = first.json()["slots"]
    assert [(s["position"], s["skill_id"], s["min_level"]) for s in slots] == [(1, str(s1.id), 3)]
    second = client.post(url, json={"skill_id": str(s2.id), "min_level": 1}, headers=auth(lead))
    assert second.status_code == 201
    assert [s["position"] for s in second.json()["slots"]] == [1, 2]


def test_remove_archives_the_row_and_frees_the_position(client, make_user, session, auth):
    lead = make_user(UserRole.LEAD)
    mission = make_mission(session, lead)
    skill = make_skill(session, lead.org_id, "S1")
    added = [add_slot(session, mission, p, skill) for p in (1, 2, 3)]
    removed_id = added[1].id
    response = client.delete(f"/missions/{mission.id}/slots/2", headers=auth(lead))
    assert response.status_code == 200
    assert [s["position"] for s in response.json()["slots"]] == [1, 3]
    session.expire_all()
    assert session.get(MissionRequirement, removed_id).archived_at is not None
    again = client.post(
        f"/missions/{mission.id}/slots",
        json={"skill_id": str(skill.id), "min_level": 2},
        headers=auth(lead),
    )
    assert again.status_code == 201
    assert [s["position"] for s in again.json()["slots"]] == [1, 2, 3]


@pytest.mark.parametrize("level", [0, 6])
def test_level_out_of_range_gives_422(client, make_user, session, level, auth):
    lead = make_user(UserRole.LEAD)
    mission = make_mission(session, lead)
    skill = make_skill(session, lead.org_id, "S1")
    response = client.post(
        f"/missions/{mission.id}/slots",
        json={"skill_id": str(skill.id), "min_level": level},
        headers=auth(lead),
    )
    assert response.status_code == 422
    assert rows(session, mission) == []


def test_unknown_or_other_org_skill_gives_422(client, make_user, session, auth):
    lead = make_user(UserRole.LEAD)
    mission = make_mission(session, lead)
    foreign = make_skill(session, make_user(UserRole.LEAD).org_id, "Foreign")
    for skill_id in (foreign.id, uuid4()):
        response = client.post(
            f"/missions/{mission.id}/slots",
            json={"skill_id": str(skill_id), "min_level": 3},
            headers=auth(lead),
        )
        assert response.status_code == 422
        assert response.json() == {"detail": f"Unknown skill: {skill_id}"}
    assert rows(session, mission) == []


def test_remove_of_a_missing_or_bad_position(client, make_user, session, auth):
    lead = make_user(UserRole.LEAD)
    mission = make_mission(session, lead)
    url = f"/missions/{mission.id}/slots"
    for position in (7, 0):
        response = client.delete(f"{url}/{position}", headers=auth(lead))
        assert response.status_code == 404
        assert response.json() == {"detail": "Not found"}
    assert client.delete(f"{url}/abc", headers=auth(lead)).status_code == 422


def test_non_owner_in_the_own_org_gets_403(client, make_user, session, auth):
    owner = make_user(UserRole.LEAD)
    org = session.get(Organization, owner.org_id)
    mission = make_mission(session, owner)
    skill = make_skill(session, owner.org_id, "S1")
    add_slot(session, mission, 1, skill)
    before = rows(session, mission)
    url = f"/missions/{mission.id}/slots"
    for other in (make_user(UserRole.LEAD, org=org), make_user(UserRole.DIRECTOR, org=org)):
        add = client.post(
            url, json={"skill_id": str(skill.id), "min_level": 2}, headers=auth(other)
        )
        remove = client.delete(f"{url}/1", headers=auth(other))
        for response in (add, remove):
            assert response.status_code == 403
            assert response.json() == {"role": other.role.value, "rule": NOT_OWNER}
    assert rows(session, mission) == before


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
def test_not_draft_gives_409_and_changes_no_slot(client, make_user, session, status, auth):
    lead = make_user(UserRole.LEAD)
    mission = make_mission(session, lead)
    skill = make_skill(session, lead.org_id, "S1")
    add_slot(session, mission, 1, skill)
    mission.status = status
    session.flush()
    before = rows(session, mission)
    url = f"/missions/{mission.id}/slots"
    add = client.post(url, json={"skill_id": str(skill.id), "min_level": 2}, headers=auth(lead))
    remove = client.delete(f"{url}/1", headers=auth(lead))
    for response in (add, remove):
        assert response.status_code == 409
        assert response.json() == {
            "detail": f"Mission is {status.value}. Edits are allowed only in DRAFT."
        }
    assert rows(session, mission) == before


def test_owner_gets_409_before_skill_check_and_non_owner_403_on_approved(
    client, make_user, session, auth
):
    owner = make_user(UserRole.LEAD)
    other = make_user(UserRole.LEAD, org=session.get(Organization, owner.org_id))
    mission = make_mission(session, owner)
    mission.status = MissionStatus.APPROVED
    session.flush()
    patch = client.patch(f"/missions/{mission.id}", json={"title": "X"}, headers=auth(other))
    assert patch.status_code == 403
    assert patch.json() == {"role": other.role.value, "rule": NOT_OWNER}
    add = client.post(
        f"/missions/{mission.id}/slots",
        json={"skill_id": str(uuid4()), "min_level": 2},
        headers=auth(owner),
    )
    assert add.status_code == 409


def test_other_org_gives_404_and_does_not_change(client, make_user, session, auth):
    director = make_user(UserRole.DIRECTOR)
    lead = make_user(UserRole.LEAD, org=session.get(Organization, director.org_id))
    other_lead = make_user(UserRole.LEAD)
    other = make_mission(session, other_lead)
    foreign = make_skill(session, other_lead.org_id, "Foreign")
    add_slot(session, other, 1, foreign)
    before = rows(session, other)
    url = f"/missions/{other.id}/slots"
    for caller in (director, lead):
        own = make_skill(session, caller.org_id, f"Own{caller.role.value}")
        add = client.post(url, json={"skill_id": str(own.id), "min_level": 2}, headers=auth(caller))
        remove = client.delete(f"{url}/1", headers=auth(caller))
        for response in (add, remove):
            assert response.status_code == 404
            assert response.json() == {"detail": "Not found"}
    assert rows(session, other) == before


def test_crew_gets_403(client, make_user, session, auth):
    crew = make_user(UserRole.CREW)
    lead = make_user(UserRole.LEAD, org=session.get(Organization, crew.org_id))
    mission = make_mission(session, lead)
    foreign = make_mission(session, make_user(UserRole.LEAD))
    skill = make_skill(session, lead.org_id, "S1")
    add_slot(session, mission, 1, skill)
    for target in (mission, foreign):
        url = f"/missions/{target.id}/slots"
        add = client.post(url, json={"skill_id": str(skill.id), "min_level": 2}, headers=auth(crew))
        remove = client.delete(f"{url}/1", headers=auth(crew))
        for response in (add, remove):
            assert response.status_code == 403
            assert response.json() == CREW_403
