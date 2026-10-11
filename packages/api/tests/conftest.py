import os
from pathlib import Path

from sqlalchemy.engine import make_url

DEV_URL = os.environ.get("DATABASE_URL", "postgresql+psycopg://mc:mc@localhost:5432/mc")
TEST_URL = make_url(DEV_URL).set(database="mc_test")
# db.py reads DATABASE_URL at import time, so set it before any mc_api import.
os.environ["DATABASE_URL"] = TEST_URL.render_as_string(hide_password=False)

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

ALEMBIC_INI = Path(__file__).resolve().parents[3] / "alembic.ini"


@pytest.fixture(scope="session")
def alembic_cfg():
    return Config(str(ALEMBIC_INI))


@pytest.fixture(scope="session", autouse=True)
def test_database(alembic_cfg):
    """Create mc_test if missing, migrate it to head, and guard the dev database."""
    dev_engine = create_engine(DEV_URL, isolation_level="AUTOCOMMIT")
    with dev_engine.connect() as conn:
        if not conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = 'mc_test'")):
            conn.execute(text("CREATE DATABASE mc_test"))

    def dev_counts():
        with dev_engine.connect() as conn:
            tables = inspect(conn).get_table_names()
            return {t: conn.scalar(text(f'SELECT count(*) FROM "{t}"')) for t in tables}

    before = dev_counts()
    command.upgrade(alembic_cfg, "head")
    yield
    assert dev_counts() == before, "a test wrote to the dev database"
    dev_engine.dispose()


@pytest.fixture
def session():
    from mc_api.db import engine

    with engine.connect() as conn:
        outer = conn.begin()
        with Session(conn, join_transaction_mode="create_savepoint") as s:
            yield s
        outer.rollback()


@pytest.fixture
def client(session):
    from fastapi.testclient import TestClient

    from mc_api.db import get_session
    from mc_api.main import app

    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def make_user(session):
    from uuid import uuid4

    from mc_api.models import AppUser, Organization

    def make(role, org=None):
        if org is None:
            org = Organization(name=f"org-{uuid4()}")
            session.add(org)
            session.flush()
        name = f"{role.lower()}-{uuid4()}"
        user = AppUser(org_id=org.id, username=name, display_name=name.title(), role=role)
        session.add(user)
        session.flush()
        return user

    return make
