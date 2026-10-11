import re

import pytest
from test_missions_cli import skill_ids

pytestmark = pytest.mark.e2e


def test_crew_journey(mc):
    assert mc("login", "--user", "ava")[0] == 0

    code, out = mc("profile", "show")
    assert code == 0
    assert all(word in out for word in ("ava", "Ava Lindqvist", "Artemis Space Agency"))

    # Spec steps 2 to 4: list, set and remove skills.
    ids = skill_ids(mc("skills", "list")[1])
    code, out = mc("profile", "skills", "list")
    assert code == 0
    assert re.search(r"Piloting\W+5", out) and re.search(r"Communications\W+4", out)

    code, out = mc("profile", "skills", "set", ids["EVA"], "--level", "2")
    assert code == 0
    assert "Set EVA to level 2" in out
    code, out = mc("profile", "skills", "set", ids["Piloting"], "--level", "4")
    assert code == 0
    assert "Set Piloting to level 4" in out
    out = mc("profile", "skills", "list")[1]
    assert re.search(r"EVA\W+2", out) and re.search(r"Piloting\W+4", out)

    code, out = mc("profile", "skills", "remove", ids["EVA"])
    assert code == 0
    assert f"Removed skill {ids['EVA']}" in out
    assert "EVA" not in mc("profile", "skills", "list")[1]

    code, out = mc("profile", "skills", "remove", "abc")
    assert code == 1
    assert "Traceback" not in out

    # Spec steps 5 and 6: add, list and remove unavailability.
    code, out = mc(
        "profile", "availability", "add",
        "--from", "2027-03-01", "--to", "2027-03-05", "--reason", "HOLIDAY",
    )  # fmt: skip
    assert code == 0
    match = re.search(r"Added unavailability ([0-9a-f-]{36})", out)
    assert match
    entry_id = match.group(1)
    code, out = mc("profile", "availability", "list")
    assert code == 0
    row = next(line for line in out.splitlines() if entry_id in line)
    assert all(word in row for word in ("2027-03-01", "2027-03-05", "HOLIDAY"))

    code, out = mc("profile", "availability", "remove", entry_id)
    assert code == 0
    assert f"Removed unavailability {entry_id}" in out
    assert entry_id not in mc("profile", "availability", "list")[1]


def test_availability_add_rejects_bad_input(mc):
    assert mc("login", "--user", "ava")[0] == 0
    add = ("profile", "availability", "add")

    code, out = mc(*add, "--from", "2027-02-30", "--to", "2027-03-01", "--reason", "SICK")
    assert code == 1
    assert "start_date" in out and "Traceback" not in out

    code, out = mc(*add, "--from", "2027-03-01", "--to", "2027-03-02", "--reason", "holiday")
    assert code == 1
    assert "reason" in out and "Traceback" not in out


def test_availability_add_requires_reason(mc):
    assert mc("login", "--user", "ava")[0] == 0
    code, out = mc("profile", "availability", "add", "--from", "2027-03-01", "--to", "2027-03-02")
    assert code != 0
    assert "--reason" in out


def test_director_is_forbidden(mc):
    assert mc("login", "--user", "diana")[0] == 0

    code, out = mc("profile", "show")
    assert code == 1
    assert "DIRECTOR" in out
    assert "Only crew members manage a profile" in out


def test_other_org_skill_is_unknown(mc):
    assert mc("login", "--user", "ava")[0] == 0
    medicine = skill_ids(mc("skills", "list")[1])["Medicine"]
    assert mc("login", "--user", "nell")[0] == 0

    code, out = mc("profile", "skills", "set", medicine, "--level", "3")
    assert code == 1
    assert "Unknown skill" in out


def test_conflicts_name_the_assignment(mc):
    assert mc("login", "--user", "hana")[0] == 0
    robotics = skill_ids(mc("skills", "list")[1])["Robotics"]

    code, out = mc("profile", "skills", "set", robotics, "--level", "2")
    assert code == 1
    assert all(word in out for word in ("Orbital Debris Survey", "INVITED", "Robotics level 3"))

    code, out = mc(
        "profile", "availability", "add",
        "--from", "2026-12-10", "--to", "2026-12-10", "--reason", "SICK",
    )  # fmt: skip
    assert code == 1
    assert "Orbital Debris Survey" in out and "2026-12-07 to 2026-12-18" in out
