from typer.testing import CliRunner

from mc_cli.main import app


def test_help_lists_top_level_commands():
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert all(c in result.output for c in ("health", "login", "whoami", "logout"))


def test_auth_commands_live_in_commands_auth():
    from mc_cli.commands import auth

    assert all(callable(getattr(auth, n)) for n in ("login", "whoami", "logout"))
