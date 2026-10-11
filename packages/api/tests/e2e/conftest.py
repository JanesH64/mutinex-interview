import os
import socket
import subprocess
import time
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from mc_api.db import SessionLocal, engine
from mc_api.seed import seed

ROOT = Path(__file__).resolve().parents[4]


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
        env = {**os.environ, "MC_API_URL": url, "MC_CONFIG_DIR": str(tmp_path), "COLUMNS": "200"}
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
