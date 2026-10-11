import os

import httpx
import typer
from rich.console import Console

from mc_cli.client import error_message, request, send
from mc_cli.token_store import delete_token, save_token
from mc_shared import Health, Me, Token

API_URL = os.environ.get("MC_API_URL", "http://localhost:8000")

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


def show(me: Me) -> str:
    return f"{me.username} ({me.display_name}), role {me.role}, org {me.org_name}"


@app.command()
def login(user: str = typer.Option(..., "--user", help="Username to log in as.")) -> None:
    """Log in and store the token."""
    response = send("POST", "/auth/login", json={"username": user})
    if response.status_code == 401:
        console.print(f"Login failed: unknown user '{user}'", markup=False)
        raise typer.Exit(1)
    if response.status_code >= 400:
        console.print(error_message(response), markup=False)
        raise typer.Exit(1)
    save_token(Token.model_validate(response.json()).access_token)
    me = Me.model_validate(request("GET", "/me").json())
    console.print(f"Logged in as {show(me)}", markup=False)


@app.command()
def whoami() -> None:
    """Show the logged-in user."""
    console.print(show(Me.model_validate(request("GET", "/me").json())), markup=False)


@app.command()
def logout() -> None:
    """Delete the stored token."""
    console.print("Logged out." if delete_token() else "Not logged in.")
