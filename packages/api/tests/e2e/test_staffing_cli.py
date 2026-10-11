import pytest
from test_matcher_cli import mission_id

pytestmark = pytest.mark.e2e


def row_with(out, text):
    return next(line for line in out.splitlines() if text in line)


def test_staffing_journey(mc):
    # Spec step 2. Later slices add steps 1, 3, 4 and 5 in the spec order.
    assert mc("login", "--user", "leo")[0] == 0
    mid = mission_id(mc("missions", "list")[1], "Mars Analogue Habitat")
    code, out = mc("missions", "invite", mid, "--slot", "2", "--crew", "ava")
    assert code == 0
    first = row_with(out, "Medicine")
    for text in ("fay", "ACCEPTED"):
        assert text in first
    second = row_with(out, "Communications")
    for text in ("ava", "INVITED"):
        assert text in second


def test_non_owner_lead_cannot_invite(mc):  # spec step 6
    assert mc("login", "--user", "leo")[0] == 0
    mid = mission_id(mc("missions", "list")[1], "Orbital Debris Survey")
    code, out = mc("missions", "invite", mid, "--slot", "1", "--crew", "ivan")
    assert code == 1
    assert "LEAD" in out
    assert "Directors and leads invite crew only to their own missions" in out


def test_invite_to_a_completed_mission_gives_409(mc):  # spec step 7
    assert mc("login", "--user", "leo")[0] == 0
    mid = mission_id(mc("missions", "list")[1], "Lunar Relay Repair")
    code, out = mc("missions", "invite", mid, "--slot", "1", "--crew", "ava")
    assert code == 1
    assert "Mission is COMPLETED. Invites are allowed only in APPROVED." in out


def test_crew_cannot_invite(mc):  # spec step 9
    assert mc("login", "--user", "leo")[0] == 0
    mid = mission_id(mc("missions", "list")[1], "Mars Analogue Habitat")
    assert mc("login", "--user", "ava")[0] == 0
    code, out = mc("missions", "invite", mid, "--slot", "2", "--crew", "ivan")
    assert code == 1
    assert "CREW" in out
    assert "Only directors and leads manage and view missions" in out


def test_other_org_lead_gets_not_found(mc):  # spec step 10
    assert mc("login", "--user", "leo")[0] == 0
    mid = mission_id(mc("missions", "list")[1], "Mars Analogue Habitat")
    assert mc("login", "--user", "nick")[0] == 0
    code, out = mc("missions", "invite", mid, "--slot", "2", "--crew", "nell")
    assert code == 1
    assert "Not found" in out
