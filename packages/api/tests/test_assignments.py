from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from test_invite import book, invite, leave
from test_invite import world as invite_world
from test_mission_slots import add_slot, make_skill
from test_profile_conflicts import assign, mission_at

from mc_api.models import AssignmentStatus, CrewSkill, MissionStatus, Organization
from mc_shared import UserRole

A = AssignmentStatus
RULE = "Only crew members view and respond to assignments"


def test_crew_lists_own_assignments_newest_mission_first(client, session, make_user, auth):
    lead = make_user(UserRole.LEAD)
    org = session.get(Organization, lead.org_id)
    c, other = make_user(UserRole.CREW, org), make_user(UserRole.CREW, org)
    skill = make_skill(session, org.id, "EVA")
    a = mission_at(session, lead, "A", date(2027, 1, 1), date(2027, 1, 5), MissionStatus.COMPLETED)
    b = mission_at(session, lead, "B", date(2027, 5, 1), date(2027, 5, 9))
    m_c = mission_at(session, lead, "C", date(2027, 5, 1), date(2027, 5, 7))
    slot_a = add_slot(session, a, 1, skill, 2)
    slot_b1, slot_b2 = add_slot(session, b, 1, skill, 1), add_slot(session, b, 2, skill, 4)
    slot_c = add_slot(session, m_c, 1, skill, 3)
    declined = assign(session, a, slot_a, c, A.DECLINED)
    declined.responded_at = datetime(2027, 1, 2, 12, tzinfo=UTC)
    invited = assign(session, b, slot_b2, c)
    accepted = assign(session, m_c, slot_c, c, A.ACCEPTED)
    assign(session, b, slot_b1, other)
    other_org = Organization(name=f"org-{uuid4()}")
    session.add(other_org)
    session.flush()
    foreign_lead = make_user(UserRole.LEAD, other_org)
    foreign_crew = make_user(UserRole.CREW, other_org)
    foreign_skill = make_skill(session, other_org.id, "EVA")
    foreign = mission_at(session, foreign_lead, "FOREIGN", date(2027, 6, 1), date(2027, 6, 5))
    foreign_slot = add_slot(session, foreign, 1, foreign_skill, 1)
    assign(session, foreign, foreign_slot, foreign_crew)
    session.flush()

    response = client.get("/assignments", headers=auth(c))

    assert response.status_code == 200
    rows = response.json()
    assert [r["mission_title"] for r in rows] == ["C", "B", "A"]
    assert [r["position"] for r in rows] == [1, 2, 1]
    assert rows[1] == {
        "id": str(invited.id),
        "mission_id": str(b.id),
        "mission_title": "B",
        "mission_status": "APPROVED",
        "start_date": "2027-05-01",
        "end_date": "2027-05-09",
        "lead_username": lead.username,
        "position": 2,
        "skill_name": "EVA",
        "min_level": 4,
        "status": "INVITED",
        "responded_at": None,
    }
    assert rows[0]["id"] == str(accepted.id)
    assert rows[0]["status"] == "ACCEPTED"
    assert rows[2]["id"] == str(declined.id)
    assert rows[2]["status"] == "DECLINED"
    assert rows[2]["mission_status"] == "COMPLETED"
    assert datetime.fromisoformat(rows[2]["responded_at"]) == declined.responded_at


def test_crew_without_assignments_gets_an_empty_list(client, make_user, auth):
    response = client.get("/assignments", headers=auth(make_user(UserRole.CREW)))
    assert response.status_code == 200
    assert response.json() == []


def test_lead_and_director_get_403(client, make_user, auth):
    for role in (UserRole.LEAD, UserRole.DIRECTOR):
        response = client.get("/assignments", headers=auth(make_user(role)))
        assert response.status_code == 403
        assert response.json() == {"role": role, "rule": RULE}


def test_list_without_token_gives_401(client):
    assert client.get("/assignments").status_code == 401


# Slice 4: accept and decline.
world = invite_world  # reuse the fixture of test_invite
NO_INVITE = {"detail": "You have no open invite for this mission."}


def respond(client, auth, user, mission_id, verb):
    return client.post(f"/assignments/{mission_id}/{verb}", headers=auth(user))


def invited(session, w, slot="slot2", status=A.INVITED):
    return assign(session, w["mission"], w[slot], w["c"], status)


def test_crew_accepts_an_invite(client, session, auth, world):
    w = world
    row = invited(session, w)
    response = respond(client, auth, w["c"], w["mission"].id, "accept")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(row.id)
    assert body["status"] == "ACCEPTED"
    assert body["responded_at"] is not None
    session.refresh(row)
    assert row.status == A.ACCEPTED
    assert row.responded_at is not None
    assert datetime.fromisoformat(body["responded_at"]) == row.responded_at


def test_crew_declines_and_the_slot_is_open_again(client, session, auth, make_user, world):
    w = world
    row = invited(session, w, "slot1")
    response = respond(client, auth, w["c"], w["mission"].id, "decline")
    assert response.status_code == 200
    assert response.json()["status"] == "DECLINED"
    assert response.json()["responded_at"] is not None
    session.refresh(row)
    assert (row.status, row.responded_at is not None) == (A.DECLINED, True)
    d = make_user(UserRole.CREW, w["org"])
    session.add(CrewSkill(org_id=d.org_id, user_id=d.id, skill_id=w["slot1"].skill_id, level=2))
    session.flush()
    assert invite(client, auth, w["lead"], w["mission"], 1, d.username).status_code == 201


@pytest.mark.parametrize("status", [A.ACCEPTED, A.DECLINED, A.CANCELLED])
@pytest.mark.parametrize("verb", ["accept", "decline"])
def test_only_an_invited_row_can_be_answered(client, session, auth, world, status, verb):
    w = world
    row = invited(session, w, status=status)
    before = row.responded_at
    response = respond(client, auth, w["c"], w["mission"].id, verb)
    assert response.status_code == 409
    assert response.json() == NO_INVITE
    session.refresh(row)
    assert (row.status, row.responded_at) == (status, before)


@pytest.mark.parametrize("verb", ["accept", "decline"])
def test_missing_rows_and_other_orgs_give_the_same_404(
    client, session, auth, make_user, world, verb
):
    w = world
    own_without_row = mission_at(session, w["lead"], "Empty", date(2027, 4, 1), date(2027, 4, 2))
    foreign_lead = make_user(UserRole.LEAD)
    foreign = mission_at(session, foreign_lead, "Foreign", date(2027, 4, 1), date(2027, 4, 2))
    for mission_id in (own_without_row.id, foreign.id, uuid4()):
        response = respond(client, auth, w["c"], mission_id, verb)
        assert response.status_code == 404
        assert response.json() == {"detail": "Not found"}


@pytest.mark.parametrize("verb", ["accept", "decline"])
def test_lead_and_director_get_403_on_respond(client, session, auth, make_user, world, verb):
    w = world
    invited(session, w)
    for role in (UserRole.LEAD, UserRole.DIRECTOR):
        user = make_user(role, w["org"])
        response = respond(client, auth, user, w["mission"].id, verb)
        assert response.status_code == 403
        assert response.json() == {"role": role, "rule": RULE}


def test_accept_rejects_double_booking(client, session, auth, world):
    w = world
    row = invited(session, w)
    book(session, w, "Short", date(2027, 3, 5), date(2027, 3, 6), A.ACCEPTED)
    response = respond(client, auth, w["c"], w["mission"].id, "accept")
    assert response.status_code == 409
    assert response.json() == {
        "detail": 'You are booked on mission "Short" from 2027-03-05 to 2027-03-06.'
    }
    session.refresh(row)
    assert (row.status, row.responded_at) == (A.INVITED, None)


def test_accept_does_not_check_skill_or_leave(client, session, auth, world):
    w = world
    invited(session, w)
    session.query(CrewSkill).filter_by(user_id=w["c"].id).update({"level": 1})
    leave(session, w, date(2027, 3, 5), date(2027, 3, 5))
    response = respond(client, auth, w["c"], w["mission"].id, "accept")
    assert response.status_code == 200
    assert response.json()["status"] == "ACCEPTED"


def test_accept_picks_the_invited_row_not_the_cancelled_one(client, session, auth, world):
    w = world
    cancelled = invited(session, w, "slot1", A.CANCELLED)
    open_row = invited(session, w, "slot2")
    response = respond(client, auth, w["c"], w["mission"].id, "accept")
    assert response.status_code == 200
    assert response.json()["id"] == str(open_row.id)
    session.refresh(cancelled)
    assert (cancelled.status, cancelled.responded_at) == (A.CANCELLED, None)


@pytest.mark.parametrize("verb", ["accept", "decline"])
def test_a_bad_mission_id_gives_422(client, auth, make_user, verb):
    response = client.post(f"/assignments/abc/{verb}", headers=auth(make_user(UserRole.CREW)))
    assert response.status_code == 422
