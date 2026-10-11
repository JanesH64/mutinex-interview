import stat

import pytest

pytestmark = pytest.mark.e2e

HINT = "Not logged in. Run: mc login --user <username>"


def test_login_whoami_logout_journey(mc):
    code, out = mc("login", "--user", "ava")
    assert code == 0
    assert all(word in out for word in ("ava", "CREW", "Artemis Space Agency"))
    assert stat.S_IMODE(mc.token.stat().st_mode) == 0o600

    code, out = mc("whoami")
    assert code == 0
    assert all(word in out for word in ("ava", "CREW", "Artemis Space Agency"))

    code, _ = mc("logout")
    assert code == 0
    assert not mc.token.exists()

    code, out = mc("whoami")
    assert code == 1
    assert HINT in out

    code, out = mc("login", "--user", "nobody")
    assert code == 1
    assert "Login failed" in out


def test_second_login_replaces_the_user(mc):
    assert mc("login", "--user", "ava")[0] == 0
    assert mc("login", "--user", "leo")[0] == 0
    assert stat.S_IMODE(mc.token.stat().st_mode) == 0o600
    code, out = mc("whoami")
    assert code == 0
    assert "leo" in out and "LEAD" in out


def test_logout_without_token(mc):
    code, out = mc("logout")
    assert code == 0
    assert "Not logged in." in out
    assert "Traceback" not in out


def test_api_down_names_the_url(mc):
    mc.token.write_text("abc")
    code, out = mc("whoami", url="http://localhost:1")
    assert code == 1
    assert "http://localhost:1" in out
    assert "Traceback" not in out
