import uuid

import pytest
from typer.testing import CliRunner

from mc_cli.commands import missions
from mc_cli.main import app


def show(monkeypatch, **extra):
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
        "slots": [],
        **extra,
    }

    class Resp:
        def json(self):
            return row

    monkeypatch.setattr(missions, "request", lambda *a, **k: Resp())
    return CliRunner().invoke(app, ["missions", "show", uid])


def test_show_prints_the_approver_in_utc(monkeypatch):
    result = show(
        monkeypatch,
        approved_by_username="dmitri",
        approved_at="2026-10-01T19:00:00+10:00",
    )
    assert result.exit_code == 0, repr(result.exception)
    assert "Approved by dmitri at 2026-10-01 09:00 UTC" in result.output


@pytest.mark.parametrize("extra", [{}, {"approved_by_username": None, "approved_at": None}])
def test_show_without_an_approver_prints_no_approved_line(monkeypatch, extra):
    result = show(monkeypatch, **extra)
    assert result.exit_code == 0, repr(result.exception)
    assert "Approved by" not in result.output
