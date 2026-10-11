import logging
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import text
from test_mission_slots import add_slot, make_skill
from test_missions import CREW_403, make_mission
from test_profile_conflicts import assign, mission_at

from mc_api.models import (
    AssignmentStatus,
    CrewSkill,
    MissionStatus,
    Organization,
    Unavailability,
)
from mc_shared import UnavailabilityReason, UserRole

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
    session.add(CrewSkill(org_id=org.id, user_id=c.id, skill_id=eva.id, level=3))
    session.flush()
    return {
        "lead": lead, "org": org, "mission": mission, "slot1": slot1, "slot2": slot2, "c": c, "eva": eva,
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


def reject(client, auth, w, detail):
    response = invite(client, auth, w["lead"], w["mission"], 2, w["c"].username)
    assert response.status_code == 409
    assert response.json() == {"detail": detail}


def set_level(session, w, level):
    row = session.get(CrewSkill, (w["c"].id, w["eva"].id))
    if level is None:
        session.delete(row)
    else:
        row.level = level
    session.flush()


def leave(session, w, start, end, reason=UnavailabilityReason.SICK):
    session.add(
        Unavailability(
            org_id=w["org"].id, user_id=w["c"].id, start_date=start, end_date=end, reason=reason
        )
    )
    session.flush()


def book(session, w, title, start, end, status=A.INVITED):
    other = mission_at(session, w["lead"], title, start, end)
    assign(session, other, add_slot(session, other, 1, w["eva"]), w["c"], status)
    return other


def test_decliner_of_this_mission_gives_409(client, session, auth, world):
    w = world
    assign(session, w["mission"], w["slot1"], w["c"], A.DECLINED)
    reject(client, auth, w, f"{w['c'].username} declined this mission.")


def test_cancelled_row_on_this_mission_still_accepts_an_invite(client, session, auth, world):
    w = world
    assign(session, w["mission"], w["slot1"], w["c"], A.CANCELLED)
    response = invite(client, auth, w["lead"], w["mission"], 2, w["c"].username)
    assert response.status_code == 201


@pytest.mark.parametrize("level, status", [(3, 201), (4, 201)])
def test_skill_at_or_above_the_minimum_level_passes(client, session, auth, world, level, status):
    set_level(session, world, level)
    w = world
    assert invite(client, auth, w["lead"], w["mission"], 2, w["c"].username).status_code == status


@pytest.mark.parametrize("level", [2, None])
def test_skill_below_the_minimum_or_missing_gives_409(client, session, auth, world, level):
    w = world
    set_level(session, w, level)
    reject(client, auth, w, f"{w['c'].username} does not have EVA at level 3 or higher.")


@pytest.mark.parametrize(
    "start, end",
    [
        (date(2027, 2, 20), date(2027, 3, 1)),
        (date(2027, 3, 10), date(2027, 3, 12)),
        (date(2027, 3, 4), date(2027, 3, 5)),
    ],
)
def test_leave_in_the_mission_dates_gives_409_without_the_reason(
    client, session, auth, world, start, end
):
    w = world
    leave(session, w, start, end)
    reject(client, auth, w, f"{w['c'].username} is unavailable from {start} to {end}.")


@pytest.mark.parametrize(
    "start, end",
    [(date(2027, 2, 15), date(2027, 2, 28)), (date(2027, 3, 11), date(2027, 3, 15))],
)
def test_leave_outside_the_mission_dates_gives_201(client, session, auth, world, start, end):
    w = world
    leave(session, w, start, end)
    assert invite(client, auth, w["lead"], w["mission"], 2, w["c"].username).status_code == 201


def test_leave_message_names_the_earliest_overlapping_leave(client, session, auth, world):
    w = world
    leave(session, w, date(2027, 3, 8), date(2027, 3, 9))
    leave(session, w, date(2027, 3, 2), date(2027, 3, 3))
    reject(client, auth, w, f"{w['c'].username} is unavailable from 2027-03-02 to 2027-03-03.")


@pytest.mark.parametrize("status", [A.INVITED, A.ACCEPTED])
def test_active_assignment_on_an_overlapping_mission_gives_409(
    client, session, auth, world, status
):
    w = world
    book(session, w, "Other", date(2027, 3, 10), date(2027, 3, 15), status)
    reject(
        client,
        auth,
        w,
        f'{w["c"].username} is booked on mission "Other" from 2027-03-10 to 2027-03-15.',
    )


@pytest.mark.parametrize("status", [A.DECLINED, A.CANCELLED])
def test_inactive_assignment_on_an_overlapping_mission_gives_201(
    client, session, auth, world, status
):
    w = world
    book(session, w, "Other", date(2027, 3, 10), date(2027, 3, 15), status)
    assert invite(client, auth, w["lead"], w["mission"], 2, w["c"].username).status_code == 201


def test_assignment_on_a_mission_that_ended_before_gives_201(client, session, auth, world):
    w = world
    book(session, w, "Before", date(2027, 2, 20), date(2027, 2, 28), A.ACCEPTED)
    assert invite(client, auth, w["lead"], w["mission"], 2, w["c"].username).status_code == 201


def test_double_booking_message_names_the_earliest_mission(client, session, auth, world):
    w = world
    book(session, w, "Late", date(2027, 3, 8), date(2027, 3, 12), A.ACCEPTED)
    book(session, w, "Early", date(2027, 3, 2), date(2027, 3, 4), A.ACCEPTED)
    reject(
        client,
        auth,
        w,
        f'{w["c"].username} is booked on mission "Early" from 2027-03-02 to 2027-03-04.',
    )


def test_one_day_mission_overlaps_leave_and_missions_on_that_day(client, session, auth, world):
    w = world
    day = date(2027, 4, 1)
    w["mission"].start_date = w["mission"].end_date = day
    session.flush()
    leave(session, w, day, day)
    reject(client, auth, w, f"{w['c'].username} is unavailable from {day} to {day}.")
    session.execute(text("DELETE FROM unavailability WHERE user_id = :u"), {"u": w["c"].id})
    book(session, w, "Same day", day, day, A.ACCEPTED)
    reject(
        client, auth, w, f'{w["c"].username} is booked on mission "Same day" from {day} to {day}.'
    )


def test_the_four_new_checks_run_in_order_after_already_on_mission(client, session, auth, world):
    w = world
    name = w["c"].username
    active = assign(session, w["mission"], w["slot1"], w["c"])
    declined = assign(session, w["mission"], w["slot2"], w["c"], A.DECLINED)
    set_level(session, w, 2)
    leave(session, w, date(2027, 3, 4), date(2027, 3, 5))
    book(session, w, "Other", date(2027, 3, 10), date(2027, 3, 15), A.ACCEPTED)
    reject(
        client, auth, w, f"{name} already has an INVITED or ACCEPTED assignment on this mission."
    )
    active.status = A.CANCELLED
    session.flush()
    reject(client, auth, w, f"{name} declined this mission.")
    session.delete(declined)
    session.flush()
    reject(client, auth, w, f"{name} does not have EVA at level 3 or higher.")
    set_level(session, w, 3)
    reject(client, auth, w, f"{name} is unavailable from 2027-03-04 to 2027-03-05.")
    session.execute(text("DELETE FROM unavailability WHERE user_id = :u"), {"u": w["c"].id})
    reject(client, auth, w, f'{name} is booked on mission "Other" from 2027-03-10 to 2027-03-15.')
