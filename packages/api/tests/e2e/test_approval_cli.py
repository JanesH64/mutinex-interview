import re

import pytest
from test_matcher_cli import mission_id

pytestmark = pytest.mark.e2e


def test_lead_submits_and_withdraws(mc):
    # Spec step 6.
    assert mc("login", "--user", "leo")[0] == 0
    code, out = mc(
        "missions", "create", "--title", "Approval Check", "--start", "2027-05-01",
        "--end", "2027-05-05",
    )  # fmt: skip
    mid = re.search(r"Created mission ([0-9a-f-]{36})", out).group(1)
    code, out = mc("missions", "submit", mid)
    assert code == 0
    assert "APPROVAL_REQUIRED" in out
    code, out = mc("missions", "withdraw", mid)
    assert code == 0
    assert "DRAFT" in out


def test_withdraw_of_an_approved_mission_exits_1(mc):
    # Spec step 7.
    assert mc("login", "--user", "leo")[0] == 0
    mid = mission_id(mc("missions", "list")[1], "Mars Analogue Habitat")
    code, out = mc("missions", "withdraw", mid)
    assert code == 1
    assert "Mission is APPROVED. Withdraw is allowed only in APPROVAL_REQUIRED." in out


def test_crew_submit_exits_1(mc):
    # Spec step 9: crew cannot list missions, so read the ID as leo first.
    assert mc("login", "--user", "leo")[0] == 0
    mid = mission_id(mc("missions", "list")[1], "Polar Ice Survey")
    assert mc("login", "--user", "ava")[0] == 0
    code, out = mc("missions", "submit", mid)
    assert code == 1
    assert "CREW" in out
    assert "Only directors and leads manage and view missions" in out


def test_bad_id_exits_1_without_traceback(mc):
    assert mc("login", "--user", "leo")[0] == 0
    code, out = mc("missions", "submit", "abc")
    assert code == 1
    assert "Traceback" not in out
