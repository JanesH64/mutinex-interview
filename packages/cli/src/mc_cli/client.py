import os

import httpx
import typer
from rich.console import Console

from mc_cli.token_store import load_token

err = Console(stderr=True, markup=False, highlight=False, soft_wrap=True)


def error_message(response: httpx.Response) -> str:
    if response.status_code == 401:
        return "Not logged in. Run: mc login --user <username>"
    return f"API error {response.status_code}: {response.text}"


def send(method: str, path: str, *, json: dict | None = None) -> httpx.Response:
    """Send one request. Exit 1 on a connection error. A status >= 400 is returned."""
    api_url = os.environ.get("MC_API_URL", "http://localhost:8000")
    token = load_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        response = httpx.request(method, f"{api_url}{path}", json=json, headers=headers)
    except httpx.HTTPError as exc:
        err.print(f"API at {api_url} is not reachable. Check MC_API_URL. ({exc})")
        raise typer.Exit(1) from None
    return response


def request(method: str, path: str, *, json: dict | None = None) -> httpx.Response:
    response = send(method, path, json=json)
    if response.status_code >= 400:
        err.print(error_message(response))
        raise typer.Exit(1)
    return response
