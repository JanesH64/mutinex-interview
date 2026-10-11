import typer
from rich.console import Console

from mc_cli.client import request
from mc_shared import ProfileOut

app = typer.Typer()
console = Console(markup=False, highlight=False, emoji=False)


@app.command()
def show() -> None:
    """Show your profile."""
    profile = ProfileOut.model_validate(request("GET", "/profile").json())
    console.print(f"{profile.username} ({profile.display_name}), org {profile.org_name}")
