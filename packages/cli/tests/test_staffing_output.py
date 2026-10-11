import uuid

from typer.testing import CliRunner

from mc_cli.commands import missions
from mc_cli.main import app


def slot(position, skill, **extra):
    return {
        "id": str(uuid.uuid4()),
        "position": position,
        "skill_id": str(uuid.uuid4()),
        "skill_name": skill,
        "min_level": 3,
        **extra,
    }


def test_show_prints_the_crew_and_status_of_each_slot(monkeypatch):
    uid = str(uuid.uuid4())
    row = {
        "id": uid,
        "title": "Polar",
        "description": None,
        "status": "APPROVED",
        "start_date": "2027-01-01",
        "end_date": "2027-01-02",
        "lead_id": uid,
        "lead_username": "leo",
        "requires_additional_director": False,
        "slots": [
            slot(1, "Medicine", crew_username="fay", assignment_status="ACCEPTED"),
            slot(2, "Communications", crew_username=None, assignment_status=None),
        ],
    }

    class Resp:
        def json(self):
            return row

    monkeypatch.setattr(missions, "request", lambda *a, **k: Resp())
    result = CliRunner().invoke(app, ["missions", "show", uid])
    assert result.exit_code == 0, repr(result.exception)
    lines = result.output.splitlines()
    header = next(line for line in lines if "Skill" in line)
    assert "Crew" in header
    assert "Status" in header
    first = next(line for line in lines if "Medicine" in line)
    assert "fay" in first
    assert "ACCEPTED" in first
    second = next(line for line in lines if "Communications" in line)
    assert "None" not in second
