import re

import pytest
from test_missions_cli import skill_ids

pytestmark = pytest.mark.e2e


def mission_id(out, title):
    return re.search(rf"([0-9a-f-]{{36}})\W+{re.escape(title)}", out).group(1)


def test_lead_matches_a_new_mission_with_no_crew(mc):
    assert mc("login", "--user", "leo")[0] == 0
    skills = skill_ids(mc("skills", "list")[1])
    code, out = mc(
        "missions",
        "create",
        "--title",
        "Deep Core Drill",
        "--start",
        "2027-05-01",
        "--end",
        "2027-05-05",
    )
    mid = re.search(r"Created mission ([0-9a-f-]{36})", out).group(1)
    assert (
        mc("missions", "slots", "add", mid, "--skill", skills["Robotics"], "--level", "5")[0] == 0
    )
    code, out = mc("missions", "match", mid)
    assert code == 0
    assert "No match" in out
    assert "0 of 1 slots filled" in out


def test_approved_mission_gives_409_message(mc):
    assert mc("login", "--user", "leo")[0] == 0
    mid = mission_id(mc("missions", "list")[1], "Mars Analogue Habitat")
    code, out = mc("missions", "match", mid)
    assert code == 1
    assert "Mission is APPROVED. The matcher preview is allowed only in DRAFT." in out


def test_other_users_get_the_error_messages(mc):
    assert mc("login", "--user", "leo")[0] == 0
    mid = mission_id(mc("missions", "list")[1], "Polar Ice Survey")
    cases = {
        "lena": ("LEAD", "Directors and leads run the matcher only on their own missions"),
        "nick": ("Not found",),
        "ava": ("CREW", "Only directors and leads manage and view missions"),
    }
    for user, expected in cases.items():
        assert mc("login", "--user", user)[0] == 0
        code, out = mc("missions", "match", mid)
        assert code == 1
        for text in expected:
            assert text in out


def test_bad_id_shows_a_message_not_a_traceback(mc):
    assert mc("login", "--user", "leo")[0] == 0
    code, out = mc("missions", "match", "abc")
    assert code == 1
    assert "Traceback" not in out


def test_unavailable_crew_not_suggested(mc):
    # Seed: cara (only EVA 4) has leave 2027-01-08..15. fay (only Medicine 4) is ACCEPTED
    # on "Mars Analogue Habitat" 2027-01-04..15.
    assert mc("login", "--user", "leo")[0] == 0
    skills = skill_ids(mc("skills", "list")[1])
    code, out = mc(
        "missions",
        "create",
        "--title",
        "Ice Window",
        "--start",
        "2027-01-11",
        "--end",
        "2027-01-14",
    )
    mid = re.search(r"Created mission ([0-9a-f-]{36})", out).group(1)
    for name in ("EVA", "Medicine"):
        add = mc("missions", "slots", "add", mid, "--skill", skills[name], "--level", "4")
        assert add[0] == 0
    code, out = mc("missions", "match", mid)
    assert code == 0
    assert out.count("No match") == 2
    assert "0 of 2 slots filled" in out
    assert "cara" not in out
    assert "fay" not in out
