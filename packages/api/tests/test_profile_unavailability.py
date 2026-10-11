from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from mc_api.models import Organization, Unavailability, UnavailabilityReason
from mc_shared import UserRole

URL = "/profile/unavailability"


def entry(user, start, end, reason):
    return Unavailability(
        org_id=user.org_id, user_id=user.id, start_date=start, end_date=end, reason=reason
    )


@pytest.fixture
def world(session, make_user):
    """Org A: crew X (2 entries, future one first) and Y (1 entry). Org B: crew with 1 entry."""
    x = make_user(UserRole.CREW)
    y = make_user(UserRole.CREW, session.get(Organization, x.org_id))
    b = make_user(UserRole.CREW)
    rows = {
        "future": entry(x, date(2027, 5, 1), date(2027, 5, 3), UnavailabilityReason.SICK),
        "past": entry(x, date(2025, 1, 10), date(2025, 1, 12), UnavailabilityReason.HOLIDAY),
        "y_entry": entry(y, date(2027, 7, 1), date(2027, 7, 2), UnavailabilityReason.MEETING),
        "b_entry": entry(b, date(2027, 7, 1), date(2027, 7, 2), UnavailabilityReason.MEETING),
    }
    session.add_all(rows.values())
    session.flush()
    return {"x": x, "y": y, "b": b, **rows}


def count(session, user):
    return session.scalar(
        select(func.count()).select_from(Unavailability).where(Unavailability.user_id == user.id)
    )


def as_json(row):
    return {
        "id": str(row.id),
        "start_date": row.start_date.isoformat(),
        "end_date": row.end_date.isoformat(),
        "reason": row.reason,
    }


def test_reason_is_shared_enum():
    import mc_api.models
    import mc_shared

    assert mc_api.models.UnavailabilityReason is mc_shared.UnavailabilityReason


def test_list_own_entries_sorted(client, world, auth):
    w = world
    response = client.get(URL, headers=auth(w["x"]))
    assert response.status_code == 200
    assert response.json() == [as_json(w["past"]), as_json(w["future"])]


def test_post_adds_one_day_entry(client, world, session, auth):
    w = world
    body = {"start_date": "2027-06-01", "end_date": "2027-06-01", "reason": "MEETING"}
    response = client.post(URL, json=body, headers=auth(w["x"]))
    assert response.status_code == 201
    assert response.json() == {"id": response.json()["id"], **body}
    assert count(session, w["x"]) == 3
    listed = client.get(URL, headers=auth(w["x"])).json()
    assert response.json() in listed


def test_post_overlapping_own_entry_is_valid(client, world, auth):
    w = world
    body = {"start_date": "2027-05-02", "end_date": "2027-05-04", "reason": "HOLIDAY"}
    assert client.post(URL, json=body, headers=auth(w["x"])).status_code == 201
    assert len(client.get(URL, headers=auth(w["x"])).json()) == 3


@pytest.mark.parametrize(
    "body",
    [
        {"start_date": "2027-06-02", "end_date": "2027-06-01", "reason": "SICK"},
        {"start_date": "2027-06-01", "end_date": "2027-06-02"},
        {"start_date": "2027-06-01", "end_date": "2027-06-02", "reason": "VACATION"},
        {"start_date": "2027-06-01", "end_date": "2027-06-02", "reason": "holiday"},
    ],
)
def test_post_invalid_is_422_and_adds_no_row(client, world, session, auth, body):
    w = world
    # The route must exist: a valid entry is accepted first.
    ok = {"start_date": "2027-06-01", "end_date": "2027-06-02", "reason": "SICK"}
    assert client.post(URL, json=ok, headers=auth(w["x"])).status_code == 201
    before = count(session, w["x"])
    response = client.post(URL, json=body, headers=auth(w["x"]))
    assert response.status_code == 422
    assert count(session, w["x"]) == before


def test_delete_own_entry(client, world, session, auth):
    w = world
    response = client.delete(f"{URL}/{w['future'].id}", headers=auth(w["x"]))
    assert response.status_code == 204
    assert response.content == b""
    ids = [e["id"] for e in client.get(URL, headers=auth(w["x"])).json()]
    assert ids == [str(w["past"].id)]
    assert count(session, w["x"]) == 1


@pytest.mark.parametrize("which", ["y", "b", "random"])
def test_delete_foreign_entry_is_404_and_row_unchanged(client, world, session, auth, which):
    w = world
    # The route must exist: the owner deletes the own entry and gets 204.
    assert client.delete(f"{URL}/{w['past'].id}", headers=auth(w["x"])).status_code == 204
    target = uuid4() if which == "random" else w[f"{which}_entry"].id
    response = client.delete(f"{URL}/{target}", headers=auth(w["x"]))
    assert response.status_code == 404
    assert response.json() == {"detail": "Not found"}
    session.expire_all()
    assert count(session, w["y"]) == 1
    assert count(session, w["b"]) == 1


def test_delete_bad_uuid_is_422(client, world, auth):
    w = world
    assert client.delete(f"{URL}/{w['past'].id}", headers=auth(w["x"])).status_code == 204
    assert client.delete(f"{URL}/abc", headers=auth(w["x"])).status_code == 422


def test_lead_is_403_and_nothing_changes(client, make_user, world, session, auth):
    w = world
    lead = make_user(UserRole.LEAD, session.get(Organization, w["x"].org_id))
    rule = {"role": UserRole.LEAD, "rule": "Only crew members manage a profile"}
    body = {"start_date": "2027-06-01", "end_date": "2027-06-02", "reason": "SICK"}
    # The route must exist: crew gets 200 on the list.
    assert client.get(URL, headers=auth(w["x"])).status_code == 200
    get = client.get(URL, headers=auth(lead))
    assert (get.status_code, get.json()) == (403, rule)
    post = client.post(URL, json=body, headers=auth(lead))
    assert (post.status_code, post.json()) == (403, rule)
    delete = client.delete(f"{URL}/{w['future'].id}", headers=auth(lead))
    assert (delete.status_code, delete.json()) == (403, rule)
    session.expire_all()
    assert count(session, w["x"]) == 2
    assert count(session, lead) == 0
