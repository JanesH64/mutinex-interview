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
    # Later slices add the next spec steps below, in order.
