import os
import subprocess
from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import text

from mc_api import db

ROOT = Path(__file__).resolve().parents[3]
TABLES = [
    "organization", "app_user", "skill", "crew_skill",
    "unavailability", "mission", "mission_requirement", "assignment",
]  # fmt: skip
WINDOW = ("2027-01-11", "2027-01-24")


def run_seed(env=None):
    return subprocess.run(
        ["uv", "run", "mc-seed"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )


def snapshot(conn):
    counts = {t: conn.scalar(text(f"SELECT count(*) FROM {t}")) for t in TABLES}
    names = set(conn.scalars(text("SELECT username FROM app_user")))
    return counts, names


@pytest.fixture(scope="module")
def conn():
    result = run_seed()
    assert result.returncode == 0, result.stderr
    with db.engine.connect() as c:
        yield c
    with db.engine.begin() as c:
        c.execute(text("TRUNCATE organization CASCADE"))


def rows(conn, sql, **params):
    return conn.execute(text(sql), params).all()


def test_seed_twice_gives_same_data(conn):
    before = snapshot(conn)
    conn.rollback()
    result = run_seed()
    assert result.returncode == 0, result.stderr
    conn.rollback()
    assert snapshot(conn) == before


def test_orgs_and_roles(conn):
    sql = """
        SELECT o.name, u.role, count(*) FROM app_user u JOIN organization o ON o.id = u.org_id
        GROUP BY 1, 2"""
    got = {(n, r): c for n, r, c in rows(conn, sql)}
    a, b = "Artemis Space Agency", "Nova Orbital"
    assert got[(a, "DIRECTOR")] == 2 and got[(a, "LEAD")] == 2 and got[(a, "CREW")] >= 8
    assert got[(b, "DIRECTOR")] == 1 and got[(b, "LEAD")] == 1 and got[(b, "CREW")] >= 3
    shared = rows(conn, "SELECT name FROM skill GROUP BY name HAVING count(DISTINCT org_id) = 2")
    assert shared
    ids = rows(conn, "SELECT count(DISTINCT id) FROM skill WHERE name = :n", n=shared[0][0])
    assert ids[0][0] == 2


ACTIVE = "a.status IN ('INVITED', 'ACCEPTED')"
RULES = {
    "non-crew skill or assignment": """
        SELECT 1 FROM crew_skill c JOIN app_user u ON u.id = c.user_id WHERE u.role <> 'CREW'
        UNION ALL
        SELECT 1 FROM assignment a JOIN app_user u ON u.id = a.user_id WHERE u.role <> 'CREW'""",
    "lead role": """
        SELECT 1 FROM mission m JOIN app_user u ON u.id = m.lead_id
        WHERE u.role NOT IN ('LEAD', 'DIRECTOR')""",
    "approver": """
        SELECT 1 FROM mission m JOIN app_user u ON u.id = m.approved_by
        WHERE u.role <> 'DIRECTOR' OR m.approved_by = m.lead_id""",
    "approval fields": """
        SELECT 1 FROM mission WHERE status IN ('APPROVED', 'COMPLETED')
        AND (approved_by IS NULL OR approved_at IS NULL)""",
    "assignment mission status": """
        SELECT 1 FROM assignment a JOIN mission m ON m.id = a.mission_id
        WHERE m.status NOT IN ('APPROVED', 'COMPLETED')""",
    "double booking": f"""
        SELECT 1 FROM assignment a JOIN mission ma ON ma.id = a.mission_id
        JOIN assignment b ON b.user_id = a.user_id AND b.id <> a.id
        JOIN mission mb ON mb.id = b.mission_id
        WHERE {ACTIVE} AND b.status IN ('INVITED', 'ACCEPTED')
        AND ma.start_date <= mb.end_date AND mb.start_date <= ma.end_date""",
    "skill level": """
        SELECT 1 FROM assignment a JOIN mission_requirement r ON r.id = a.requirement_id
        WHERE NOT EXISTS (SELECT 1 FROM crew_skill c WHERE c.user_id = a.user_id
        AND c.skill_id = r.skill_id AND c.level >= r.min_level)""",
}


@pytest.mark.parametrize("rule", RULES)
def test_data_obeys_rules(conn, rule):
    assert rows(conn, RULES[rule]) == []


def test_matcher_scenarios(conn):
    start, end = WINDOW
    org = "(SELECT id FROM organization WHERE name = 'Artemis Space Agency')"

    def levels(skill):
        sql = f"""SELECT c.level FROM crew_skill c JOIN skill s ON s.id = c.skill_id
            WHERE s.name = :s AND s.org_id = {org}"""
        return {r[0] for r in rows(conn, sql, s=skill)}

    assert {5, 3} <= levels("Piloting")

    leave = rows(
        conn,
        f"""SELECT 1 FROM unavailability n JOIN crew_skill c ON c.user_id = n.user_id
        JOIN skill s ON s.id = c.skill_id
        WHERE s.name = 'EVA' AND c.level >= 3 AND n.org_id = {org}
        AND n.start_date <= :e AND :s <= n.end_date""",
        s=start, e=end,
    )  # fmt: skip
    assert leave

    booked = rows(
        conn,
        f"""SELECT 1 FROM assignment a JOIN mission m ON m.id = a.mission_id
        JOIN crew_skill c ON c.user_id = a.user_id JOIN skill s ON s.id = c.skill_id
        WHERE s.name = 'Medicine' AND c.level >= 2 AND {ACTIVE} AND a.org_id = {org}
        AND m.start_date <= :e AND :s <= m.end_date""",
        s=start, e=end,
    )  # fmt: skip
    assert booked

    sql = f"""
        SELECT c.user_id, c.level,
          (SELECT coalesce(sum(least(m.end_date, DATE '2027-03-25')
              - greatest(m.start_date, DATE '2026-11-12') + 1), 0)
           FROM assignment a JOIN mission m ON m.id = a.mission_id
           WHERE a.user_id = c.user_id AND {ACTIVE}
           AND m.start_date <= DATE '2027-03-25' AND m.end_date >= DATE '2026-11-12') AS days
        FROM crew_skill c JOIN skill s ON s.id = c.skill_id
        WHERE s.name = 'EVA' AND c.level >= 3 AND c.org_id = {org}
        AND NOT EXISTS (SELECT 1 FROM unavailability n WHERE n.user_id = c.user_id
            AND n.start_date <= :e AND :s <= n.end_date)
        AND NOT EXISTS (SELECT 1 FROM assignment a JOIN mission m ON m.id = a.mission_id
            WHERE a.user_id = c.user_id AND {ACTIVE}
            AND m.start_date <= :e AND :s <= m.end_date)"""
    free = rows(conn, sql, s=start, e=end)
    by_level = {}
    for _, level, days in free:
        by_level.setdefault(level, []).append(days)
    assert any(len(d) >= 2 and 0 in d and any(x > 0 for x in d) for d in by_level.values())


def test_history_rows(conn):
    assert rows(conn, "SELECT 1 FROM assignment WHERE status = 'DECLINED'")
    sql = """SELECT 1 FROM assignment a JOIN mission m ON m.id = a.mission_id
        WHERE a.status = 'ACCEPTED' AND m.status = 'COMPLETED' AND m.end_date < DATE '2026-10-11'"""
    assert rows(conn, sql)
    late = rows(
        conn,
        """SELECT 1 FROM assignment WHERE responded_at >= TIMESTAMPTZ '2026-10-11 00:00+00'
        UNION ALL SELECT 1 FROM mission WHERE approved_at >= TIMESTAMPTZ '2026-10-11 00:00+00'""",
    )
    assert late == []


def test_second_org_has_all_kinds(conn):
    org = "(SELECT id FROM organization WHERE name = 'Nova Orbital')"
    for table in TABLES[2:]:
        assert rows(conn, f"SELECT 1 FROM {table} WHERE org_id = {org} LIMIT 1"), table


def test_seed_without_schema_fails_clearly(conn, alembic_cfg):
    conn.rollback()
    conn.close()
    try:
        command.downgrade(alembic_cfg, "base")
        result = run_seed()
    finally:
        command.upgrade(alembic_cfg, "head")
    assert result.returncode == 1
    out = result.stdout + result.stderr
    assert "uv run alembic upgrade head" in out
    assert "Traceback" not in out


def test_seed_without_postgres_fails_clearly():
    url = "postgresql+psycopg://mc:secret@localhost:1/mc"
    result = run_seed({"DATABASE_URL": url})
    assert result.returncode == 1
    out = result.stdout + result.stderr
    assert "docker compose up -d" in out
    assert "Traceback" not in out
    assert "secret" not in out
