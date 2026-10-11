from alembic import command
from sqlalchemy import inspect, text

from mc_api import db

TABLES = {
    "organization", "app_user", "skill", "crew_skill",
    "unavailability", "mission", "mission_requirement", "assignment",
}  # fmt: skip
ENUMS = {
    "user_role": ["DIRECTOR", "LEAD", "CREW"],
    "mission_status": [
        "DRAFT",
        "APPROVAL_REQUIRED",
        "APPROVED",
        "ACTIVE",
        "COMPLETED",
        "CANCELLED",
    ],
    "assignment_status": ["INVITED", "ACCEPTED", "DECLINED", "CANCELLED"],
    "unavailability_reason": ["HOLIDAY", "SICK", "MEETING"],
}


def enum_values(conn):
    rows = conn.execute(
        text(
            "SELECT t.typname, e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid"
            " ORDER BY t.typname, e.enumsortorder"
        )
    )
    out: dict[str, list[str]] = {}
    for name, label in rows:
        out.setdefault(name, []).append(label)
    return out


def test_uses_test_database():
    assert db.engine.url.database == "mc_test"


def test_head_has_tables_and_enums():
    with db.engine.connect() as conn:
        assert TABLES <= set(inspect(conn).get_table_names())
        assert enum_values(conn) == ENUMS


def test_check_finds_no_diff(alembic_cfg):
    command.check(alembic_cfg)


def test_downgrade_then_upgrade(alembic_cfg):
    try:
        command.downgrade(alembic_cfg, "base")
        with db.engine.connect() as conn:
            assert not TABLES & set(inspect(conn).get_table_names())
            assert enum_values(conn) == {}
    finally:
        command.upgrade(alembic_cfg, "head")
