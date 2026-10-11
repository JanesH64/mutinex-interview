from urllib.parse import quote

import typer
from rich.console import Console
from rich.table import Table

from mc_cli.client import request
from mc_shared import MissionOut, MissionSummary

app = typer.Typer()
console = Console(markup=False, highlight=False, emoji=False)


def print_mission(m: MissionOut) -> None:
    console.print(f"Mission {m.id}")
    console.print(m.title)
    console.print(m.status)
    console.print(f"{m.start_date} to {m.end_date}")
    console.print(m.lead_username)
    if m.requires_additional_director:
        console.print("This mission needs an additional director for approval.")
    table = Table("Slot", "Skill", "Min level")
    for slot in m.slots:
        table.add_row(str(slot.position), slot.skill_name, str(slot.min_level))
    console.print(table)


@app.command()
def create(
    title: str = typer.Option(..., "--title"),
    start: str = typer.Option(..., "--start", help="Start date, YYYY-MM-DD."),
    end: str = typer.Option(..., "--end", help="End date, YYYY-MM-DD."),
    description: str | None = typer.Option(None, "--description"),
) -> None:
    """Create a DRAFT mission that you lead."""
    # Dates go as text, so the API checks them.
    body = {"title": title, "start_date": start, "end_date": end, "description": description}
    mission = MissionOut.model_validate(request("POST", "/missions", json=body).json())
    console.print(f"Created mission {mission.id}")
    print_mission(mission)


@app.command("list")
def list_missions() -> None:
    """List the missions of your org."""
    table = Table("ID", "Title", "Status", "Start", "End", "Lead")
    table.columns[0].no_wrap = True
    for item in request("GET", "/missions").json():
        m = MissionSummary.model_validate(item)
        table.add_row(
            str(m.id), m.title, m.status, str(m.start_date), str(m.end_date), m.lead_username
        )
    console.print(table)


@app.command()
def show(mission_id: str) -> None:
    """Show a mission and its slots."""
    print_mission(
        MissionOut.model_validate(request("GET", f"/missions/{quote(mission_id, safe='')}").json())
    )


@app.command()
def edit(
    mission_id: str,
    title: str | None = typer.Option(None, "--title"),
    description: str | None = typer.Option(None, "--description"),
    start: str | None = typer.Option(None, "--start", help="Start date, YYYY-MM-DD."),
    end: str | None = typer.Option(None, "--end", help="End date, YYYY-MM-DD."),
) -> None:
    """Edit a DRAFT mission that you lead. Only the given options change."""
    given = {"title": title, "description": description, "start_date": start, "end_date": end}
    body = {k: v for k, v in given.items() if v is not None}
    path = f"/missions/{quote(mission_id, safe='')}"
    print_mission(MissionOut.model_validate(request("PATCH", path, json=body).json()))


slots = typer.Typer()
app.add_typer(slots, name="slots", help="Add and remove slots of a DRAFT mission.")


@slots.command("add")
def add_slot(
    mission_id: str,
    skill: str = typer.Option(..., "--skill", help="Skill ID."),
    level: int = typer.Option(..., "--level", help="Minimum level, 1 to 5."),
) -> None:
    """Add a slot to a DRAFT mission that you lead."""
    path = f"/missions/{quote(mission_id, safe='')}/slots"
    body = {"skill_id": skill, "min_level": level}
    print_mission(MissionOut.model_validate(request("POST", path, json=body).json()))


@slots.command("remove")
def remove_slot(mission_id: str, position: str) -> None:
    """Remove the slot at a position from a DRAFT mission that you lead."""
    path = f"/missions/{quote(mission_id, safe='')}/slots/{quote(position, safe='')}"
    print_mission(MissionOut.model_validate(request("DELETE", path).json()))
