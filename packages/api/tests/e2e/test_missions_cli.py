import re

import pytest

pytestmark = pytest.mark.e2e


def skill_ids(out: str) -> dict[str, str]:
    """Map each skill name to its UUID from `mc skills list` output."""
    return {name: uid for uid, name in re.findall(r"([0-9a-f-]{36})\W+(\w+)", out)}


def test_lead_journey(mc):
    # Spec step 1: the lead lists the skills of the own org.
    assert mc("login", "--user", "leo")[0] == 0
    code, out = mc("skills", "list")
    assert code == 0
    skills = skill_ids(out)
    for name in ("Piloting", "EVA", "Medicine", "Robotics", "Geology", "Communications"):
        assert name in skills
    assert "Welding" not in out
    # Spec step 2: the lead creates a mission.
    code, out = mc(
        "missions",
        "create",
        "--title",
        "Ice Core Drill",
        "--start",
        "2027-03-01",
        "--end",
        "2027-03-10",
    )
    assert code == 0
    created = re.search(r"Created mission ([0-9a-f-]{36})", out)
    assert created
    assert "DRAFT" in out
    assert "additional director" not in out
    mission_id = created.group(1)
    # Spec step 3: the lead adds two slots.
    for name, level in (("Piloting", "3"), ("Geology", "2")):
        code, out = mc(
            "missions", "slots", "add", mission_id, "--skill", skills[name], "--level", level
        )
        assert code == 0
    assert re.search(r"\b1\b.*Piloting", out)
    assert re.search(r"\b2\b.*Geology", out)
    # Spec step 4: the lead removes slot 1, then the next add reuses position 1.
    assert mc("missions", "slots", "remove", mission_id, "1")[0] == 0
    code, out = mc("missions", "slots", "add", mission_id, "--skill", skills["EVA"], "--level", "3")
    assert code == 0
    assert re.search(r"\b1\b.*EVA", out)
    assert re.search(r"\b2\b.*Geology", out)
    # Spec step 5: the lead edits the own mission.
    code, out = mc("missions", "edit", mission_id, "--title", "Ice Core Drill II")
    assert code == 0
    assert "Ice Core Drill II" in out
    # Spec step 6: list and show.
    code, out = mc("missions", "list")
    assert code == 0
    for title in (
        "Ice Core Drill",
        "Lunar Relay Repair",
        "Orbital Debris Survey",
        "Mars Analogue Habitat",
    ):
        assert title in out
    code, out = mc("missions", "show", mission_id)
    assert code == 0
    assert "Ice Core Drill II" in out
    assert "leo" in out
    assert "EVA" in out
    assert "Geology" in out


def test_other_org_sees_not_found(mc):
    assert mc("login", "--user", "leo")[0] == 0
    code, out = mc(
        "missions", "create", "--title", "Private", "--start", "2027-03-01", "--end", "2027-03-10"
    )
    assert code == 0
    mission_id = re.search(r"Created mission ([0-9a-f-]{36})", out).group(1)
    assert mc("login", "--user", "nick")[0] == 0
    code, out = mc("missions", "show", mission_id)
    assert code == 1
    assert "Not found" in out


def test_crew_is_forbidden(mc):
    assert mc("login", "--user", "ava")[0] == 0
    code, out = mc("missions", "list")
    assert code == 1
    assert "CREW" in out
    assert "Only directors and leads manage and view missions" in out


def test_director_mission_needs_additional_director(mc):
    assert mc("login", "--user", "diana")[0] == 0
    code, out = mc(
        "missions",
        "create",
        "--title",
        "Deep Field Survey",
        "--start",
        "2027-04-01",
        "--end",
        "2027-04-05",
    )
    assert code == 0
    assert "This mission needs an additional director for approval." in out


def test_bad_input_shows_a_message_not_a_traceback(mc):
    assert mc("login", "--user", "leo")[0] == 0
    code, out = mc("missions", "show", "abc")
    assert code == 1
    assert "Traceback" not in out
    assert "mission_id" in out
    code, out = mc(
        "missions", "create", "--title", "X", "--start", "2027-13-01", "--end", "2027-12-31"
    )
    assert code == 1
    assert "start_date" in out
    assert "Traceback" not in out
