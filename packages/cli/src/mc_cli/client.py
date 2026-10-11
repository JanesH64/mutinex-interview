import os
from typing import NoReturn

import httpx
import typer
from rich.console import Console

from mc_cli.token_store import load_token
from mc_shared import ForbiddenError

err = Console(stderr=True, markup=False, highlight=False, emoji=False, soft_wrap=True)


API_URL = os.environ.get("MC_API_URL", "http://localhost:8000")


def error_message(response: httpx.Response) -> str:
    if response.status_code == 401:
        return "Not logged in. Run: mc login --user <username>"
    if response.status_code == 403:
        try:
            body = ForbiddenError.model_validate(response.json())
        except ValueError:  # not our API, for example a proxy page
            return f"API error 403: {response.text}"
        return f"Forbidden: your role is {body.role}. Rule: {body.rule}"
    if response.status_code == 404:
        return "Not found"
    if response.status_code in (409, 422):
        try:
            detail = response.json()["detail"]
        except (ValueError, KeyError, TypeError):
            detail = None
        if isinstance(detail, str):
            return detail
        if response.status_code == 422 and isinstance(detail, list):
            return "\n".join(f"{d['loc'][-1]}: {d['msg']}" for d in detail)
    return f"API error {response.status_code}: {response.text}"


def send(method: str, path: str, *, json: dict | None = None) -> httpx.Response:
    """Send one request. Exit 1 on a connection error. A status >= 400 is returned."""
    token = load_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        response = httpx.request(method, f"{API_URL}{path}", json=json, headers=headers)
    except httpx.HTTPError as exc:
        err.print(f"API at {API_URL} is not reachable. Check MC_API_URL. ({exc})")
        raise typer.Exit(1) from None
    return response


def fail(response: httpx.Response) -> NoReturn:
    err.print(error_message(response))
    raise typer.Exit(1)


def request(method: str, path: str, *, json: dict | None = None) -> httpx.Response:
    response = send(method, path, json=json)
    if response.status_code >= 400:
        fail(response)
    return response
