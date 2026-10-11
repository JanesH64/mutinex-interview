import httpx
import typer
from rich.console import Console

from mc_cli.client import API_URL
from mc_cli.commands import auth
from mc_shared import Health

app = typer.Typer(no_args_is_help=True)
console = Console()


@app.callback()
def main() -> None:
    """Mission Control CLI."""


@app.command()
def health() -> None:
    """Check that the API and the database are up."""
    try:
        response = httpx.get(f"{API_URL}/health")
        response.raise_for_status()
    except httpx.HTTPError as exc:
        console.print(f"[red]API at {API_URL} is not reachable:[/red] {exc}")
        raise typer.Exit(1)
    result = Health.model_validate(response.json())
    console.print(f"[green]API {result.status}[/green], database {result.db} ({API_URL})")


app.command()(auth.login)
app.command()(auth.whoami)
app.command()(auth.logout)
