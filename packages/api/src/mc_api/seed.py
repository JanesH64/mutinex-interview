"""Demo data for `mc-seed`. It deletes all rows of the 8 tables first."""

import sys
import uuid
from datetime import UTC, date, datetime

import psycopg.errors
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from mc_api.db import SessionLocal, engine
from mc_api.models import (
    AppUser,
    Assignment,
    AssignmentStatus,
    CrewSkill,
    Mission,
    MissionRequirement,
    MissionStatus,
    Organization,
    Skill,
    Unavailability,
    UnavailabilityReason,
    UserRole,
)

TABLES = [
    "assignment", "mission_requirement", "mission", "unavailability",
    "crew_skill", "skill", "app_user", "organization",
]  # fmt: skip

SKILLS = {
    "A": ["Piloting", "EVA", "Medicine", "Robotics", "Geology", "Communications"],
    "B": ["Piloting", "EVA", "Welding"],
}
# (org, username, display name, role, {skill: level})
USERS = [
    ("A", "diana", "Diana Reyes", "DIRECTOR", {}),
    ("A", "dmitri", "Dmitri Volkov", "DIRECTOR", {}),
    ("A", "leo", "Leo Hart", "LEAD", {}),
    ("A", "lena", "Lena Okafor", "LEAD", {}),
    ("A", "ava", "Ava Lindqvist", "CREW", {"Piloting": 5, "Communications": 4}),
    ("A", "ben", "Ben Carter", "CREW", {"Piloting": 3, "Geology": 2}),
    ("A", "cara", "Cara Novak", "CREW", {"EVA": 4, "Robotics": 3}),
    ("A", "dev", "Dev Patel", "CREW", {"EVA": 3}),
    ("A", "eli", "Eli Moreau", "CREW", {"EVA": 3, "Geology": 3}),
    ("A", "fay", "Fay Adeyemi", "CREW", {"Medicine": 4}),
    ("A", "gus", "Gus Brandt", "CREW", {"Medicine": 2}),
    ("A", "hana", "Hana Sato", "CREW", {"Medicine": 3, "Robotics": 4}),
    ("A", "ivan", "Ivan Petrov", "CREW", {"Piloting": 4, "Communications": 3}),
    ("A", "jo", "Jo Kim", "CREW", {"Geology": 4, "Communications": 2}),
    ("B", "nora", "Nora Quinn", "DIRECTOR", {}),
    ("B", "nick", "Nick Alvarez", "LEAD", {}),
    ("B", "nell", "Nell Foster", "CREW", {"Piloting": 4, "EVA": 3}),
    ("B", "ned", "Ned Ito", "CREW", {"EVA": 4, "Welding": 3}),
    ("B", "nia", "Nia Banda", "CREW", {"Welding": 5}),
]
# (org, user, from, to, reason)
LEAVE = [
    ("A", "cara", date(2027, 1, 8), date(2027, 1, 15), "HOLIDAY"),
    ("A", "ivan", date(2026, 11, 2), date(2026, 11, 4), "SICK"),
    ("A", "hana", date(2027, 2, 3), date(2027, 2, 3), "MEETING"),
    ("B", "nell", date(2026, 12, 21), date(2027, 1, 3), "HOLIDAY"),
]


def at(month: int, day: int, hour: int = 0, year: int = 2026) -> datetime:
    return datetime(year, month, day, hour, tzinfo=UTC)


# (org, title, status, start, end, lead, approver, approved_at,
#  slots [(skill, min_level)], assignments [(slot position, user, status, responded_at)])
MISSIONS = [
    ("A", "Lunar Relay Repair", "COMPLETED", date(2026, 9, 7), date(2026, 9, 18), "leo",
     "diana", at(8, 20, 9),
     [("Piloting", 3), ("Geology", 3), ("Medicine", 2)],
     [(1, "ivan", "ACCEPTED", at(8, 24)), (2, "jo", "ACCEPTED", at(8, 24)),
      (3, "hana", "DECLINED", at(8, 23)), (3, "gus", "ACCEPTED", at(8, 26))]),
    ("A", "Orbital Debris Survey", "APPROVED", date(2026, 12, 7), date(2026, 12, 18), "lena",
     "dmitri", at(10, 1, 9),
     [("EVA", 3), ("Robotics", 3)],
     [(1, "dev", "ACCEPTED", at(10, 5)), (2, "hana", "INVITED", None)]),
    ("A", "Mars Analogue Habitat", "APPROVED", date(2027, 1, 4), date(2027, 1, 15), "leo",
     "dmitri", at(10, 2, 9),
     [("Medicine", 3), ("Communications", 3)],
     [(1, "fay", "ACCEPTED", at(10, 6))]),
    ("B", "Station Truss Assembly", "APPROVED", date(2027, 1, 11), date(2027, 1, 22), "nick",
     "nora", at(10, 2, 9),
     [("Welding", 3), ("EVA", 3)],
     [(1, "nia", "INVITED", None), (2, "ned", "ACCEPTED", at(10, 7))]),
]  # fmt: skip


def seed(session: Session) -> None:
    """Delete all rows of the 8 tables, then add the demo dataset. Does not commit."""
    session.execute(text(f"TRUNCATE {', '.join(TABLES)}"))
    orgs = {}
    for key, name in (("A", "Artemis Space Agency"), ("B", "Nova Orbital")):
        orgs[key] = Organization(id=uuid.uuid4(), name=name)
    session.add_all(orgs.values())
    session.flush()  # the models have no relationships, so flush each level in order
    skills = {
        (o, n): Skill(id=uuid.uuid4(), org_id=orgs[o].id, name=n)
        for o, names in SKILLS.items()
        for n in names
    }
    users = {
        u: AppUser(id=uuid.uuid4(), org_id=orgs[o].id, username=u, display_name=d, role=UserRole(r))
        for o, u, d, r, _ in USERS
    }
    session.add_all([*skills.values(), *users.values()])
    session.flush()

    session.add_all(
        CrewSkill(org_id=orgs[o].id, user_id=users[u].id, skill_id=skills[o, s].id, level=level)
        for o, u, _, _, profile in USERS
        for s, level in profile.items()
    )
    session.add_all(
        Unavailability(
            id=uuid.uuid4(), org_id=orgs[o].id, user_id=users[u].id,
            start_date=start, end_date=end, reason=UnavailabilityReason(reason),
        )
        for o, u, start, end, reason in LEAVE
    )  # fmt: skip

    for o, title, status, start, end, lead, approver, approved_at, slots, assignments in MISSIONS:
        mission = Mission(
            id=uuid.uuid4(), org_id=orgs[o].id, title=title, lead_id=users[lead].id,
            status=MissionStatus(status), start_date=start, end_date=end,
            approved_by=users[approver].id, approved_at=approved_at,
        )  # fmt: skip
        slot_rows = [
            MissionRequirement(
                id=uuid.uuid4(), org_id=orgs[o].id, mission_id=mission.id, position=pos,
                skill_id=skills[o, s].id, min_level=level,
            )
            for pos, (s, level) in enumerate(slots, 1)
        ]  # fmt: skip
        session.add(mission)
        session.flush()
        session.add_all(slot_rows)
        session.flush()
        session.add_all(
            Assignment(
                id=uuid.uuid4(), org_id=orgs[o].id, mission_id=mission.id,
                requirement_id=slot_rows[pos - 1].id, user_id=users[u].id,
                status=AssignmentStatus(st), responded_at=responded,
            )
            for pos, u, st, responded in assignments
        )  # fmt: skip
        session.flush()


def main() -> None:
    """Entry point of `mc-seed`. Runs seed() in one transaction and commits. Exits 1 on a DB error."""
    try:
        with SessionLocal() as session:
            seed(session)
            session.commit()
            counts = {
                t: session.scalar(text(f"SELECT count(*) FROM {t}")) for t in reversed(TABLES)
            }
    except OperationalError:
        url = engine.url.render_as_string(hide_password=True)
        print(
            f"Cannot reach the database at {url}. Start Postgres: docker compose up -d",
            file=sys.stderr,
        )
        sys.exit(1)
    except ProgrammingError as error:
        if not isinstance(error.orig, psycopg.errors.UndefinedTable):
            raise
        print("The schema is missing. Run: uv run alembic upgrade head", file=sys.stderr)
        sys.exit(1)
    print("Seeded: " + ", ".join(f"{t} {n}" for t, n in counts.items()))
