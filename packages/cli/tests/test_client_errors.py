import httpx

from mc_cli.client import error_message


def response(status, **kwargs):
    return httpx.Response(status, request=httpx.Request("GET", "http://x/"), **kwargs)


def test_401_shows_the_login_hint():
    assert error_message(response(401)) == "Not logged in. Run: mc login --user <username>"
