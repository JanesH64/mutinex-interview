import re
import uuid

from typer.testing import CliRunner

from mc_cli.commands import missions
from mc_cli.main import app
from mc_shared import SlotOut


def slot(position, skill, level):
    return SlotOut(
        id=uuid.uuid4(), position=position, skill_id=uuid.uuid4(), skill_name=skill, min_level=level
    )


def test_match_prints_the_table_and_the_summary(monkeypatch):
    from mc_shared import CrewSuggestion, MatchPreview, SlotMatch

    mission_id = uuid.uuid4()
    ben = CrewSuggestion(
        user_id=uuid.uuid4(), username="ben", display_name="Ben", level=3, workload_days=0
    )
    preview = MatchPreview(
        mission_id=mission_id,
        slots=[
            SlotMatch(slot=slot(1, "Piloting", 3), suggestion=ben),
            SlotMatch(slot=slot(2, "Medicine", 2), suggestion=None),
        ],
    )

    class Resp:
        def json(self):
            return preview.model_dump(mode="json")

    monkeypatch.setattr(missions, "request", lambda *a, **k: Resp())
    result = CliRunner().invoke(app, ["missions", "match", str(mission_id)])
    assert result.exit_code == 0, repr(result.exception)
    lines = result.output.splitlines()
    filled = next(line for line in lines if "Piloting" in line)
    assert re.search(r"\b1\b.*Piloting.*\b3\b.*ben.*\b3\b.*\b0\b", filled)
    empty = next(line for line in lines if "Medicine" in line)
    assert "2" in empty and "No match" in empty
    assert lines[-1].strip() == "1 of 2 slots filled"
