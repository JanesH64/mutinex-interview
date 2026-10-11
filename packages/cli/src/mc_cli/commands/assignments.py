from datetime import UTC
from urllib.parse import quote

import typer
from rich.console import Console
from rich.table import Table

from mc_cli.client import request
from mc_shared import AssignmentOut

app = typer.Typer()
console = Console(markup=False, highlight=False, emoji=False)


@app.command("list")
def list_assignments() -> None:
    """List your assignments, with history."""
    table = Table("Mission ID", "Title", "Start", "End", "Slot", "Skill", "Status", "Responded")
    for column in table.columns:
        column.min_width = len(column.header)
    table.columns[0].no_wrap = True
    for item in request("GET", "/assignments").json():
        a = AssignmentOut.model_validate(item)
        responded = (
            a.responded_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M") if a.responded_at else ""
        )
        table.add_row(
            str(a.mission_id),
            a.mission_title,
            str(a.start_date),
            str(a.end_date),
            str(a.position),
            a.skill_name,
            a.status,
            responded,
        )
    # The table is wider than 80 columns with a full UUID. Keep each header whole.
    if not console.is_terminal:
        console.width = max(console.width, 120)
    console.print(table)


def respond(action: str, mission_id: str) -> None:
    a = AssignmentOut.model_validate(
        request("POST", f"/assignments/{quote(mission_id, safe='')}/{action}").json()
    )
    console.print(f"{a.status}: {a.mission_title}, slot {a.position} {a.skill_name}")


@app.command()
def accept(mission_id: str) -> None:
    """Accept your invite to a mission."""
    respond("accept", mission_id)


@app.command()
def decline(mission_id: str) -> None:
    """Decline your invite to a mission."""
    respond("decline", mission_id)
