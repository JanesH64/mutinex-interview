import stat

from mc_cli.token_store import delete_token, load_token, save_token, token_path


def mode(path):
    return stat.S_IMODE(path.stat().st_mode)


def test_save_load_delete(tmp_path, monkeypatch):
    monkeypatch.setenv("MC_CONFIG_DIR", str(tmp_path / "cfg"))
    save_token("abc")
    path = token_path()
    assert path == tmp_path / "cfg" / "token"
    assert path.read_text() == "abc"
    assert mode(path) == 0o600
    assert load_token() == "abc"
    assert delete_token() is True
    assert not path.exists()
    assert load_token() is None
    assert delete_token() is False


def test_second_save_replaces_token_and_keeps_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("MC_CONFIG_DIR", str(tmp_path))
    save_token("one")
    save_token("two")
    assert token_path().read_text() == "two"
    assert mode(token_path()) == 0o600


def test_older_file_with_wide_mode_gets_0600(tmp_path, monkeypatch):
    monkeypatch.setenv("MC_CONFIG_DIR", str(tmp_path))
    (tmp_path / "token").write_text("old")
    (tmp_path / "token").chmod(0o644)
    save_token("new")
    assert mode(token_path()) == 0o600


def test_empty_file_gives_none(tmp_path, monkeypatch):
    monkeypatch.setenv("MC_CONFIG_DIR", str(tmp_path))
    (tmp_path / "token").write_text("")
    assert load_token() is None
