import threading
from datetime import date
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from mc_api.auth import create_token
from mc_api.db import engine
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
)
from mc_shared import UserRole

CLEANUP = (
    "assignment",
    "mission_requirement",
    "crew_skill",
    "mission",
    "skill",
    "app_user",
)


def test_invite_waits_for_the_crew_lock_and_sees_committed_data():
    from fastapi.testclient import TestClient

    from mc_api.main import app

    org = Organization(name=f"org-{uuid4()}")
    with Session(engine) as s:
        s.add(org)
        s.flush()
        users = {
            role: AppUser(
                org_id=org.id, username=f"{role.lower()}-{uuid4()}", display_name="X", role=role
            )
            for role in (UserRole.LEAD, UserRole.CREW)
        }
        s.add_all(users.values())
        skill = Skill(org_id=org.id, name="EVA")
        s.add(skill)
        s.flush()
        lead, crew = users[UserRole.LEAD], users[UserRole.CREW]
        s.add(CrewSkill(org_id=org.id, user_id=crew.id, skill_id=skill.id, level=3))
        missions = []
        for title, start in (("First", date(2027, 3, 1)), ("Second", date(2027, 3, 5))):
            m = Mission(
                org_id=org.id,
                title=title,
                lead_id=lead.id,
                status=MissionStatus.APPROVED,
                start_date=start,
                end_date=date(2027, 3, 10),
            )
            s.add(m)
            s.flush()
            s.add(
                MissionRequirement(
                    org_id=org.id, mission_id=m.id, position=1, skill_id=skill.id, min_level=3
                )
            )
            missions.append(m)
        s.flush()
        first_id, second_id = missions[0].id, missions[1].id
        second_slot = s.scalar(
            text("SELECT id FROM mission_requirement WHERE mission_id = :m"), {"m": second_id}
        )
        lead_id, crew_id, crew_name = lead.id, crew.id, crew.username
        org_id = org.id
        s.commit()

    result = {}

    def send():
        response = TestClient(app).post(
            f"/missions/{first_id}/assignments",
            json={"position": 1, "username": crew_name},
            headers={"Authorization": f"Bearer {create_token(lead_id)}"},
        )
        result["response"] = response

    try:
        with Session(engine) as x:
            x.execute(text("SELECT id FROM app_user WHERE id = :u FOR UPDATE"), {"u": crew_id})
            thread = threading.Thread(target=send)
            thread.start()
            thread.join(0.5)
            assert thread.is_alive(), "the invite did not wait for the crew user lock"
            x.add(
                Assignment(
                    org_id=org_id,
                    mission_id=second_id,
                    requirement_id=second_slot,
                    user_id=crew_id,
                    status=AssignmentStatus.INVITED,
                )
            )
            x.commit()
        thread.join(10)
        assert not thread.is_alive()
        response = result["response"]
        assert response.status_code == 409
        assert response.json() == {
            "detail": f'{crew_name} is booked on mission "Second" from 2027-03-05 to 2027-03-10.'
        }
    finally:
        with engine.begin() as conn:
            for table in CLEANUP:
                conn.execute(text(f"DELETE FROM {table} WHERE org_id = :o"), {"o": org_id})
            conn.execute(text("DELETE FROM organization WHERE id = :o"), {"o": org_id})


def test_accept_waits_for_the_crew_lock_and_sees_committed_data():
    from fastapi.testclient import TestClient

    from mc_api.main import app

    org = Organization(name=f"org-{uuid4()}")
    with Session(engine) as s:
        s.add(org)
        s.flush()
        lead = AppUser(org_id=org.id, username=f"lead-{uuid4()}", display_name="X", role="LEAD")
        crew = AppUser(org_id=org.id, username=f"crew-{uuid4()}", display_name="X", role="CREW")
        s.add_all([lead, crew])
        skill = Skill(org_id=org.id, name="EVA")
        s.add(skill)
        s.flush()
        slots, mission_ids = [], []
        for title, start in (("First", date(2027, 3, 1)), ("Second", date(2027, 3, 5))):
            m = Mission(
                org_id=org.id,
                title=title,
                lead_id=lead.id,
                status=MissionStatus.APPROVED,
                start_date=start,
                end_date=date(2027, 3, 10),
            )
            s.add(m)
            s.flush()
            slot = MissionRequirement(
                org_id=org.id, mission_id=m.id, position=1, skill_id=skill.id, min_level=3
            )
            s.add(slot)
            s.flush()
            mission_ids.append(m.id)
            slots.append(slot.id)
        s.add(
            Assignment(
                org_id=org.id,
                mission_id=mission_ids[0],
                requirement_id=slots[0],
                user_id=crew.id,
                status=AssignmentStatus.INVITED,
            )
        )
        crew_id, org_id = crew.id, org.id
        s.commit()

    result = {}

    def send():
        result["response"] = TestClient(app).post(
            f"/assignments/{mission_ids[0]}/accept",
            headers={"Authorization": f"Bearer {create_token(crew_id)}"},
        )

    try:
        with Session(engine) as x:
            x.execute(text("SELECT id FROM app_user WHERE id = :u FOR UPDATE"), {"u": crew_id})
            thread = threading.Thread(target=send)
            thread.start()
            thread.join(0.5)
            assert thread.is_alive(), "the accept did not wait for the crew user lock"
            x.add(
                Assignment(
                    org_id=org_id,
                    mission_id=mission_ids[1],
                    requirement_id=slots[1],
                    user_id=crew_id,
                    status=AssignmentStatus.ACCEPTED,
                )
            )
            x.commit()
        thread.join(10)
        assert not thread.is_alive()
        response = result["response"]
        assert response.status_code == 409
        assert response.json() == {
            "detail": 'You are booked on mission "Second" from 2027-03-05 to 2027-03-10.'
        }
    finally:
        with engine.begin() as conn:
            for table in CLEANUP:
                conn.execute(text(f"DELETE FROM {table} WHERE org_id = :o"), {"o": org_id})
            conn.execute(text("DELETE FROM organization WHERE id = :o"), {"o": org_id})
