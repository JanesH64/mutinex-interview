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
