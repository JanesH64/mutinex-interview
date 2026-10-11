from uuid import uuid4

import pytest
from sqlalchemy import func, select

from mc_api.models import CrewSkill, Organization, Skill
from mc_shared import UserRole


@pytest.fixture
def world(session, make_user):
    """Org A: skills Zeta and Alpha, crew X (Zeta 2, Alpha 4) and Y (Alpha 1). Org B: crew and a skill."""
    x = make_user(UserRole.CREW)
    y = make_user(UserRole.CREW, session.get(Organization, x.org_id))
    zeta = Skill(org_id=x.org_id, name="Zeta")
    alpha = Skill(org_id=x.org_id, name="Alpha")
    extra = Skill(org_id=x.org_id, name="Extra")
    b = make_user(UserRole.CREW)
    b_skill = Skill(org_id=b.org_id, name="Bskill")
    session.add_all([zeta, alpha, extra, b_skill])
    session.flush()
    session.add_all(
        [
            CrewSkill(org_id=x.org_id, user_id=x.id, skill_id=zeta.id, level=2),
            CrewSkill(org_id=x.org_id, user_id=x.id, skill_id=alpha.id, level=4),
            CrewSkill(org_id=x.org_id, user_id=y.id, skill_id=alpha.id, level=1),
        ]
    )
    session.flush()
    return {
        "x": x,
        "y": y,
        "b": b,
        "zeta": zeta,
        "alpha": alpha,
        "extra": extra,
        "b_skill": b_skill,
    }


def count(session, user):
    return session.scalar(
        select(func.count()).select_from(CrewSkill).where(CrewSkill.user_id == user.id)
    )


def test_list_own_skills_sorted_by_name(client, world, auth):
    w = world
    response = client.get("/profile/skills", headers=auth(w["x"]))
    assert response.status_code == 200
    assert response.json() == [
        {"skill_id": str(w["alpha"].id), "skill_name": "Alpha", "level": 4},
        {"skill_id": str(w["zeta"].id), "skill_name": "Zeta", "level": 2},
    ]


def test_put_adds_new_skill(client, world, auth):
    w = world
    url = f"/profile/skills/{w['extra'].id}"
    response = client.put(url, json={"level": 3}, headers=auth(w["x"]))
    assert response.status_code == 200
    assert response.json() == {"skill_id": str(w["extra"].id), "skill_name": "Extra", "level": 3}
    listed = client.get("/profile/skills", headers=auth(w["x"])).json()
    assert {"skill_id": str(w["extra"].id), "skill_name": "Extra", "level": 3} in listed


def test_put_changes_level_without_new_row(client, world, session, auth):
    w = world
    before = count(session, w["x"])
    response = client.put(
        f"/profile/skills/{w['alpha'].id}", json={"level": 5}, headers=auth(w["x"])
    )
    assert response.status_code == 200
    assert response.json()["level"] == 5
    assert count(session, w["x"]) == before
    listed = client.get("/profile/skills", headers=auth(w["x"])).json()
    assert {"skill_id": str(w["alpha"].id), "skill_name": "Alpha", "level": 5} in listed
    session.expire_all()
    assert session.get(CrewSkill, (w["y"].id, w["alpha"].id)).level == 1


@pytest.mark.parametrize("body", [{"level": 0}, {"level": 6}, {}, {"level": "x"}, {"level": 2.5}])
def test_put_bad_level_is_422(client, world, auth, body):
    w = world
    response = client.put(f"/profile/skills/{w['extra'].id}", json=body, headers=auth(w["x"]))
    assert response.status_code == 422


@pytest.mark.parametrize("which", ["org_b", "missing"])
def test_put_unknown_skill_is_422(client, world, session, auth, which):
    w = world
    skill_id = w["b_skill"].id if which == "org_b" else uuid4()
    before = count(session, w["x"])
    response = client.put(f"/profile/skills/{skill_id}", json={"level": 3}, headers=auth(w["x"]))
    assert response.status_code == 422
    assert response.json() == {"detail": f"Unknown skill: {skill_id}"}
    assert count(session, w["x"]) == before


def test_delete_removes_skill(client, world, auth):
    w = world
    response = client.delete(f"/profile/skills/{w['zeta'].id}", headers=auth(w["x"]))
    assert response.status_code == 204
    assert response.content == b""
    names = [s["skill_name"] for s in client.get("/profile/skills", headers=auth(w["x"])).json()]
    assert "Zeta" not in names


def test_delete_skill_not_in_profile_is_404(client, world, auth):
    w = world
    response = client.delete(f"/profile/skills/{w['extra'].id}", headers=auth(w["x"]))
    assert response.status_code == 404
    assert response.json() == {"detail": "Not found"}


def test_delete_other_org_is_404_and_row_unchanged(client, world, session, auth):
    w = world
    # The route must exist: the owner deletes a skill and gets 204.
    session.add(CrewSkill(org_id=w["y"].org_id, user_id=w["y"].id, skill_id=w["zeta"].id, level=3))
    session.flush()
    own = client.delete(f"/profile/skills/{w['zeta'].id}", headers=auth(w["y"]))
    assert own.status_code == 204
    response = client.delete(f"/profile/skills/{w['alpha'].id}", headers=auth(w["b"]))
    assert response.status_code == 404
    assert response.json() == {"detail": "Not found"}
    row = session.get(CrewSkill, (w["y"].id, w["alpha"].id))
    assert row is not None and row.level == 1


def test_non_uuid_skill_id_is_422(client, world, auth):
    h = auth(world["x"])
    assert client.put("/profile/skills/abc", json={"level": 3}, headers=h).status_code == 422
    assert client.delete("/profile/skills/abc", headers=h).status_code == 422


def test_director_is_403_and_nothing_changes(client, make_user, world, session, auth):
    w = world
    director = make_user(UserRole.DIRECTOR, session.get(Organization, w["x"].org_id))
    rule = {"role": UserRole.DIRECTOR, "rule": "Only crew members manage a profile"}
    before = count(session, w["x"])
    put = client.put(f"/profile/skills/{w['extra'].id}", json={"level": 3}, headers=auth(director))
    assert (put.status_code, put.json()) == (403, rule)
    delete = client.delete(f"/profile/skills/{w['zeta'].id}", headers=auth(director))
    assert (delete.status_code, delete.json()) == (403, rule)
    assert count(session, w["x"]) == before
