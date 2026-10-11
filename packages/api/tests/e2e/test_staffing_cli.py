import pytest
from test_matcher_cli import mission_id

pytestmark = pytest.mark.e2e


def row_with(out, text):
    return next(line for line in out.splitlines() if text in line)


def test_staffing_journey(mc):
    # Spec steps 1 to 4 (first parts). Later slices add the rest in the spec order.
    assert mc("login", "--user", "leo")[0] == 0
    mid = mission_id(mc("missions", "list")[1], "Mars Analogue Habitat")
    code, out = mc("missions", "invite", mid, "--slot", "2", "--crew", "jo")
    assert code == 1
    assert "jo does not have Communications at level 3 or higher." in out
    code, out = mc("missions", "invite", mid, "--slot", "2", "--crew", "ava")
    assert code == 0
    first = row_with(out, "Medicine")
    for text in ("fay", "ACCEPTED"):
        assert text in first
    second = row_with(out, "Communications")
    for text in ("ava", "INVITED"):
        assert text in second
    # Spec step 3, first part.
    assert mc("login", "--user", "ava")[0] == 0
    code, out = mc("assignments", "list")
    assert code == 0
    mars = row_with(out, "Mars Analogue Habitat")
    assert "INVITED" in mars
    # Spec step 4, first part.
    assert mc("login", "--user", "hana")[0] == 0
    code, out = mc("assignments", "list")
    assert code == 0
    assert "INVITED" in row_with(out, "Orbital Debris Survey")
    assert "DECLINED" in row_with(out, "Lunar Relay Repair")


def test_lead_cannot_list_assignments(mc):  # spec step 8
    assert mc("login", "--user", "leo")[0] == 0
    code, out = mc("assignments", "list")
    assert code == 1
    assert "LEAD" in out
    assert "Only crew members view and respond to assignments" in out


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
