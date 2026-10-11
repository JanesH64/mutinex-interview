import httpx
import pytest
import typer

from mc_cli import client
from mc_cli.client import error_message


def response(status, **kwargs):
    return httpx.Response(status, request=httpx.Request("GET", "http://x/"), **kwargs)


def test_401_shows_the_login_hint():
    assert error_message(response(401)) == "Not logged in. Run: mc login --user <username>"


def test_403_shows_role_and_rule():
    body = {"role": "CREW", "rule": "Crew members view only their own profile"}
    message = error_message(response(403, json=body))
    assert "CREW" in message
    assert "Crew members view only their own profile" in message


def test_404_says_not_found():
    assert error_message(response(404)) == "Not found"


def test_403_with_unexpected_body_does_not_raise():
    assert "403" in error_message(response(403, text="<html>blocked</html>"))


@pytest.mark.parametrize("status", [403, 404])
def test_request_exits_1_for_403_and_404(monkeypatch, capsys, status):
    body = {"role": "CREW", "rule": "Crew members view only their own profile"}
    monkeypatch.setattr(client.httpx, "request", lambda *a, **k: response(status, json=body))
    with pytest.raises(typer.Exit) as exc:
        client.request("GET", "/x")
    assert exc.value.exit_code == 1
    err = capsys.readouterr().err
    assert ("CREW" in err and "Crew members view only" in err) or "Not found" in err


def test_422_with_a_list_detail_shows_field_and_message():
    detail = [
        {
            "loc": ["body", "start_date"],
            "msg": "Input should be a valid date",
            "type": "date_from_datetime_parsing",
        },
        {"loc": ["body", "title"], "msg": "Field required", "type": "missing"},
    ]
    message = error_message(response(422, json={"detail": detail}))
    assert "start_date: Input should be a valid date" in message
    assert "title: Field required" in message


def test_422_with_a_text_detail_shows_the_text():
    assert "Unknown skill: abc" in error_message(
        response(422, json={"detail": "Unknown skill: abc"})
    )


def test_409_shows_the_detail():
    detail = "Mission is APPROVED. Edits are allowed only in DRAFT."
    assert detail in error_message(response(409, json={"detail": detail}))


@pytest.mark.parametrize(
    ("status", "kwargs", "text"),
    [
        (
            409,
            {"json": {"detail": "Mission is APPROVED. Edits are allowed only in DRAFT."}},
            "Mission is APPROVED",
        ),
        (422, {"json": {"detail": "Unknown skill: abc"}}, "Unknown skill: abc"),
    ],
)
def test_request_exits_1_for_409_and_422(monkeypatch, capsys, status, kwargs, text):
    monkeypatch.setattr(client.httpx, "request", lambda *a, **k: response(status, **kwargs))
    with pytest.raises(typer.Exit) as exc:
        client.request("GET", "/x")
    assert exc.value.exit_code == 1
    assert text in capsys.readouterr().err


def test_request_exits_1_for_a_redirect(monkeypatch):
    monkeypatch.setattr(client.httpx, "request", lambda *a, **k: response(307, text=""))
    with pytest.raises(typer.Exit) as exc:
        client.request("GET", "/missions/")
    assert exc.value.exit_code == 1
