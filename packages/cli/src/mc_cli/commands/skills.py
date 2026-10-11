import typer
from rich.console import Console
from rich.table import Table

from mc_cli.client import request
from mc_shared import SkillOut

app = typer.Typer()
console = Console(markup=False, highlight=False, emoji=False)


@app.command("list")
def list_skills() -> None:
    """List the skills of your org."""
    table = Table("ID", "Name", "Description")
    table.columns[0].no_wrap = True
    for item in request("GET", "/skills").json():
        skill = SkillOut.model_validate(item)
        table.add_row(str(skill.id), skill.name, skill.description or "")
    console.print(table)
