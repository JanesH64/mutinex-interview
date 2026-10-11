from urllib.parse import quote

import typer
from rich.console import Console
from rich.table import Table

from mc_cli.client import request
from mc_shared import CrewSkillOut, ProfileOut

app = typer.Typer()
console = Console(markup=False, highlight=False, emoji=False)


@app.command()
def show() -> None:
    """Show your profile."""
    profile = ProfileOut.model_validate(request("GET", "/profile").json())
    console.print(f"{profile.username} ({profile.display_name}), org {profile.org_name}")


skills = typer.Typer()
app.add_typer(skills, name="skills", help="List, set and remove your skills.")


@skills.command("list")
def list_skills() -> None:
    """List your skills."""
    table = Table("Skill ID", "Skill", "Level")
    table.columns[0].no_wrap = True
    for item in request("GET", "/profile/skills").json():
        s = CrewSkillOut.model_validate(item)
        table.add_row(str(s.skill_id), s.skill_name, str(s.level))
    console.print(table)


@skills.command("set")
def set_skill(skill_id: str, level: int = typer.Option(..., "--level")) -> None:
    """Add a skill or change its level."""
    path = f"/profile/skills/{quote(skill_id, safe='')}"
    s = CrewSkillOut.model_validate(request("PUT", path, json={"level": level}).json())
    console.print(f"Set {s.skill_name} to level {s.level}")


@skills.command()
def remove(skill_id: str) -> None:
    """Remove a skill from your profile."""
    request("DELETE", f"/profile/skills/{quote(skill_id, safe='')}")
    console.print(f"Removed skill {skill_id}")
