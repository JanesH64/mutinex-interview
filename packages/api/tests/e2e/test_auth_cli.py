import os
import socket
import stat
import subprocess
import time
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from mc_api.db import SessionLocal, engine
from mc_api.seed import seed

pytestmark = pytest.mark.e2e

ROOT = Path(__file__).resolve().parents[4]
HINT = "Not logged in. Run: mc login --user <username>"


@pytest.fixture(scope="module")
def api_url():
    with SessionLocal() as s:
        seed(s)
        s.commit()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    proc = subprocess.Popen(
        ["uv", "run", "uvicorn", "mc_api.main:app", "--port", str(port)], cwd=ROOT
    )
    try:
        deadline = time.monotonic() + 20
        while True:
            try:
                if httpx.get(f"{url}/health").status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            assert time.monotonic() < deadline, "uvicorn did not start"
            time.sleep(0.2)
        yield url
    finally:
        proc.terminate()
        proc.wait()
        with engine.begin() as c:
            c.execute(text("TRUNCATE organization CASCADE"))


@pytest.fixture
def mc(api_url, tmp_path):
    def run(*args, url=api_url):
        env = {**os.environ, "MC_API_URL": url, "MC_CONFIG_DIR": str(tmp_path)}
        result = subprocess.run(
            ["uv", "run", "mc", *args],
            check=False,
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        return result.returncode, result.stdout + result.stderr

    run.token = tmp_path / "token"
    return run


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
