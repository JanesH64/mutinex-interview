import uuid

from typer.testing import CliRunner

from mc_cli.commands import skills
from mc_cli.main import app


def test_skills_list_prints_markup_like_text_literally(monkeypatch):
    rows = [
        {"id": str(uuid.uuid4()), "name": "A [/x]", "description": None},
        {"id": str(uuid.uuid4()), "name": "B", "description": "[red]r[/red]"},
    ]

    class Resp:
        def json(self):
            return rows

    monkeypatch.setattr(skills, "request", lambda *a, **k: Resp())
    result = CliRunner().invoke(app, ["skills", "list"])
    assert result.exit_code == 0, repr(result.exception)
    assert "A [/x]" in result.output
    assert "[red]r[/red]" in result.output
