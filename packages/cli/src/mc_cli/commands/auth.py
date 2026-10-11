import typer
from rich.console import Console

from mc_cli.client import err, fail, request, send
from mc_cli.token_store import delete_token, save_token
from mc_shared import Me, Token

console = Console(markup=False, highlight=False, emoji=False)


def show(me: Me) -> str:
    return f"{me.username} ({me.display_name}), role {me.role}, org {me.org_name}"


def login(user: str = typer.Option(..., "--user", help="Username to log in as.")) -> None:
    """Log in and store the token."""
    response = send("POST", "/auth/login", json={"username": user})
    if response.status_code == 401:
        err.print(f"Login failed: unknown user '{user}'")
        raise typer.Exit(1)
    if response.status_code >= 400:
        fail(response)
    save_token(Token.model_validate(response.json()).access_token)
    me = Me.model_validate(request("GET", "/me").json())
    console.print(f"Logged in as {show(me)}")


def whoami() -> None:
    """Show the logged-in user."""
    console.print(show(Me.model_validate(request("GET", "/me").json())))


def logout() -> None:
    """Delete the stored token."""
    console.print("Logged out." if delete_token() else "Not logged in.")
