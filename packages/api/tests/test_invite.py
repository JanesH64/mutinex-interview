import logging
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import text
from test_mission_slots import add_slot, make_skill
from test_missions import CREW_403, make_mission
from test_profile_conflicts import assign

from mc_api.models import AssignmentStatus, MissionStatus, Organization
from mc_shared import UserRole

S = MissionStatus
A = AssignmentStatus
NOT_OWNER = "Directors and leads invite crew only to their own missions"
ROLE_422 = "{} is not a crew member. Only crew members can be assigned to missions."


@pytest.fixture
def world(session, make_user):
    lead = make_user(UserRole.LEAD)
    org = session.get(Organization, lead.org_id)
    mission = make_mission(session, lead)
    mission.start_date, mission.end_date = date(2027, 3, 1), date(2027, 3, 10)
    mission.status = S.APPROVED
    eva = make_skill(session, lead.org_id, "EVA")
    slot1 = add_slot(session, mission, 1, make_skill(session, lead.org_id, "Medicine"), 2)
    slot2 = add_slot(session, mission, 2, eva, 3)
    c = make_user(UserRole.CREW, org)
    session.flush()
    return {
        "lead": lead, "org": org, "mission": mission, "slot1": slot1, "slot2": slot2, "c": c,
    }  # fmt: skip


def invite(client, auth, user, mission, position=2, username=None, **body):
    payload = {"position": position, "username": username, **body}
    return client.post(f"/missions/{mission.id}/assignments", json=payload, headers=auth(user))


def count(session):
    return session.scalar(text("SELECT count(*) FROM assignment"))


def slot_of(response, position):
    return next(s for s in response.json()["slots"] if s["position"] == position)


def test_lead_invites_a_crew_member(client, session, auth, world):
    w = world
    response = invite(client, auth, w["lead"], w["mission"], 2, w["c"].username)
    assert response.status_code == 201
    slot = slot_of(response, 2)
    assert slot["crew_username"] == w["c"].username
    assert slot["assignment_status"] == "INVITED"
    # No test assumes empty tables, so filter by mission.
    rows = session.execute(
        text("SELECT status, responded_at, requirement_id FROM assignment WHERE mission_id = :m"),
        {"m": w["mission"].id},
    ).all()
    assert len(rows) == 1
    assert rows[0].status == "INVITED"
    assert rows[0].responded_at is None
    assert rows[0].requirement_id == w["slot2"].id


def test_director_who_leads_the_mission_invites(client, make_user, session, auth, world):
    w = world
    director = make_user(UserRole.DIRECTOR, w["org"])
    w["mission"].lead_id = director.id
    session.flush()
    response = invite(client, auth, director, w["mission"], 2, w["c"].username)
    assert response.status_code == 201
    assert slot_of(response, 2)["assignment_status"] == "INVITED"


def test_non_owner_in_the_own_org_gets_403(client, make_user, session, auth, world):
    w = world
    before = count(session)
    for other in (make_user(UserRole.LEAD, w["org"]), make_user(UserRole.DIRECTOR, w["org"])):
        response = invite(client, auth, other, w["mission"], 2, w["c"].username)
        assert response.status_code == 403
        assert response.json() == {"role": other.role.value, "rule": NOT_OWNER}
    assert count(session) == before


def test_crew_gets_403(client, session, auth, world):
    w = world
    before = count(session)
    response = invite(client, auth, w["c"], w["mission"], 2, w["c"].username)
    assert response.status_code == 403
    assert response.json() == CREW_403
    assert count(session) == before


@pytest.mark.parametrize(
    "status", [S.DRAFT, S.APPROVAL_REQUIRED, S.ACTIVE, S.COMPLETED, S.CANCELLED]
)
def test_wrong_status_gives_409(client, session, auth, world, status):
    w = world
    w["mission"].status = status
    session.flush()
    response = invite(client, auth, w["lead"], w["mission"], 2, w["c"].username)
    assert response.status_code == 409
    assert response.json() == {
        "detail": f"Mission is {status.value}. Invites are allowed only in APPROVED."
    }


def test_other_org_gives_the_same_404_as_a_missing_id(client, make_user, session, auth, world):
    w = world
    director = make_user(UserRole.DIRECTOR, w["org"])
    other = make_mission(session, make_user(UserRole.LEAD))
    other.status = S.APPROVED
    session.flush()
    missing = type("M", (), {"id": uuid4()})
    for caller in (w["lead"], director):
        expected = invite(client, auth, caller, missing, 2, w["c"].username)
        response = invite(client, auth, caller, other, 2, w["c"].username)
        assert response.status_code == expected.status_code == 404
        assert response.json() == expected.json() == {"detail": "Not found"}


def test_unknown_slot_gives_422(client, auth, world):
    w = world
    response = invite(client, auth, w["lead"], w["mission"], 9, w["c"].username)
    assert response.status_code == 422
    assert response.json() == {"detail": "Unknown slot: 9"}


def test_archived_slot_gives_422(client, session, auth, world):
    w = world
    w["slot1"].archived_at = w["mission"].created_at
    session.flush()
    response = invite(client, auth, w["lead"], w["mission"], 1, w["c"].username)
    assert response.status_code == 422
    assert response.json() == {"detail": "Unknown slot: 1"}


def test_unknown_username_gives_422(client, auth, world):
    w = world
    name = f"nobody-{uuid4()}"
    response = invite(client, auth, w["lead"], w["mission"], 2, name)
    assert response.status_code == 422
    assert response.json() == {"detail": f"Unknown crew member: {name}"}


def test_crew_of_another_org_gives_the_unknown_body(client, make_user, auth, world):
    w = world
    stranger = make_user(UserRole.CREW)
    response = invite(client, auth, w["lead"], w["mission"], 2, stranger.username)
    assert response.status_code == 422
    assert response.json() == {"detail": f"Unknown crew member: {stranger.username}"}


@pytest.mark.parametrize("role", [UserRole.LEAD, UserRole.DIRECTOR])
def test_non_crew_username_gives_422(client, make_user, auth, world, role):
    w = world
    other = make_user(role, w["org"])
    response = invite(client, auth, w["lead"], w["mission"], 2, other.username)
    assert response.status_code == 422
    assert response.json() == {"detail": ROLE_422.format(other.username)}


@pytest.mark.parametrize("status", [A.INVITED, A.ACCEPTED])
def test_filled_slot_gives_409(client, make_user, session, auth, world, status):
    w = world
    assign(session, w["mission"], w["slot2"], make_user(UserRole.CREW, w["org"]), status)
    response = invite(client, auth, w["lead"], w["mission"], 2, w["c"].username)
    assert response.status_code == 409
    assert response.json() == {"detail": "Slot 2 already has an INVITED or ACCEPTED assignment."}


def test_slot_with_only_declined_and_cancelled_rows_accepts_an_invite(
    client, make_user, session, auth, world
):
    w = world
    assign(session, w["mission"], w["slot2"], make_user(UserRole.CREW, w["org"]), A.DECLINED)
    assign(session, w["mission"], w["slot2"], make_user(UserRole.CREW, w["org"]), A.CANCELLED)
    response = invite(client, auth, w["lead"], w["mission"], 2, w["c"].username)
    assert response.status_code == 201
    slot = slot_of(response, 2)
    assert slot["crew_username"] == w["c"].username
    assert slot["assignment_status"] == "INVITED"


def test_crew_member_on_another_slot_gives_409(client, session, auth, world):
    w = world
    assign(session, w["mission"], w["slot1"], w["c"])
    response = invite(client, auth, w["lead"], w["mission"], 2, w["c"].username)
    assert response.status_code == 409
    assert response.json() == {
        "detail": f"{w['c'].username} already has an INVITED or ACCEPTED assignment on this mission."
    }


@pytest.mark.parametrize("position, detail", [(0, "Unknown slot: 0"), (-1, "Unknown slot: -1")])
def test_non_positive_position_gives_unknown_slot(client, auth, world, position, detail):
    w = world
    response = invite(client, auth, w["lead"], w["mission"], position, w["c"].username)
    assert response.status_code == 422
    assert response.json() == {"detail": detail}


def test_bad_bodies_give_422(client, auth, world):
    w = world
    url = f"/missions/{w['mission'].id}/assignments"
    headers = auth(w["lead"])
    assert (
        client.post(url, json={"position": "abc", "username": "x"}, headers=headers).status_code
        == 422
    )
    assert client.post(url, json={"position": 2}, headers=headers).status_code == 422


def test_username_match_is_case_sensitive(client, auth, world):
    w = world
    name = w["c"].username.upper()
    response = invite(client, auth, w["lead"], w["mission"], 2, name)
    assert response.status_code == 422
    assert response.json() == {"detail": f"Unknown crew member: {name}"}


def test_mission_view_shows_the_active_assignment_of_each_slot(
    client, make_user, session, auth, world
):
    w = world
    a = make_user(UserRole.CREW, w["org"])
    assign(session, w["mission"], w["slot1"], a, A.ACCEPTED)
    assign(session, w["mission"], w["slot2"], make_user(UserRole.CREW, w["org"]), A.DECLINED)
    response = client.get(f"/missions/{w['mission'].id}", headers=auth(w["lead"]))
    assert response.status_code == 200
    first, second = slot_of(response, 1), slot_of(response, 2)
    assert (first["crew_username"], first["assignment_status"]) == (a.username, "ACCEPTED")
    assert second["crew_username"] is None
    assert second["assignment_status"] is None


def test_invite_and_rejection_write_info_logs(client, make_user, auth, world, caplog):
    w = world
    caplog.set_level(logging.INFO)
    ok = invite(client, auth, w["lead"], w["mission"], 2, w["c"].username)
    assert ok.status_code == 201
    ok_records = [r for r in caplog.records if r.name.startswith("mc_api.")]
    assert ok_records
    caplog.clear()
    bad = invite(
        client, auth, w["lead"], w["mission"], 2, make_user(UserRole.CREW, w["org"]).username
    )
    assert bad.status_code == 409
    assert [r for r in caplog.records if r.name.startswith("mc_api.")]
    assert all("Bearer" not in r.getMessage() for r in caplog.records)
    assert all("Bearer" not in r.getMessage() for r in ok_records)


def test_match_preview_of_a_draft_mission_is_unchanged(client, auth, world, session):
    w = world
    w["mission"].status = S.DRAFT
    session.flush()
    response = client.get(f"/missions/{w['mission'].id}/match", headers=auth(w["lead"]))
    assert response.status_code == 200
    assert [m["slot"]["position"] for m in response.json()["slots"]] == [1, 2]
