import pytest

pytestmark = pytest.mark.e2e


def test_crew_journey(mc):
    assert mc("login", "--user", "ava")[0] == 0

    code, out = mc("profile", "show")
    assert code == 0
    assert all(word in out for word in ("ava", "Ava Lindqvist", "Artemis Space Agency"))


def test_director_is_forbidden(mc):
    assert mc("login", "--user", "diana")[0] == 0

    code, out = mc("profile", "show")
    assert code == 1
    assert "DIRECTOR" in out
    assert "Only crew members manage a profile" in out
