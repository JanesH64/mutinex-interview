from datetime import UTC, datetime

from test_missions import make_mission

from mc_api.models import Organization
from mc_shared import UserRole


def test_view_shows_the_approver(client, make_user, session, auth):
    lead = make_user(UserRole.LEAD)
    d2 = make_user(UserRole.DIRECTOR, org=session.get(Organization, lead.org_id))
    mission = make_mission(session, lead)
    at = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
    mission.approved_by = d2.id
    mission.approved_at = at
    session.flush()
    body = client.get(f"/missions/{mission.id}", headers=auth(lead)).json()
    assert body["approved_by_username"] == d2.username
    assert datetime.fromisoformat(body["approved_at"]) == at


def test_view_of_a_never_approved_mission_has_null_approver(client, make_user, session, auth):
    lead = make_user(UserRole.LEAD)
    mission = make_mission(session, lead)
    body = client.get(f"/missions/{mission.id}", headers=auth(lead)).json()
    assert body["approved_by_username"] is None
    assert body["approved_at"] is None
