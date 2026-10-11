import uuid

from typer.testing import CliRunner

from mc_cli.commands import skills
from mc_cli.main import app


def test_skills_list_prints_markup_like_text_literally(monkeypatch):
    rows = [
        {"id": str(uuid.uuid4()), "name": "A [/x]", "description": None},
        {"id": str(uuid.uuid4()), "name": "B", "description": "[red]r[/red] :fire:"},
    ]

    class Resp:
        def json(self):
            return rows

    monkeypatch.setattr(skills, "request", lambda *a, **k: Resp())
    result = CliRunner().invoke(app, ["skills", "list"])
    assert result.exit_code == 0, repr(result.exception)
    assert "A [/x]" in result.output
    assert "[red]r[/red] :fire:" in result.output


def test_mission_show_prints_emoji_codes_literally(monkeypatch):
    from mc_cli.commands import missions

    uid = str(uuid.uuid4())
    row = {
        "id": uid,
        "title": "Check :fire: alarm",
        "description": None,
        "status": "DRAFT",
        "start_date": "2027-01-01",
        "end_date": "2027-01-02",
        "lead_id": uid,
        "lead_username": "leo",
        "requires_additional_director": False,
        "slots": [],
    }

    class Resp:
        def json(self):
            return row

    monkeypatch.setattr(missions, "request", lambda *a, **k: Resp())
    result = CliRunner().invoke(app, ["missions", "show", uid])
    assert result.exit_code == 0, repr(result.exception)
    assert "Check :fire: alarm" in result.output
