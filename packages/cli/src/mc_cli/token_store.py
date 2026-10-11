import os
from pathlib import Path


def token_path() -> Path:
    return Path(os.environ.get("MC_CONFIG_DIR", "~/.config/mc")).expanduser() / "token"


def save_token(token: str) -> None:
    path = token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)  # An older file can have a wider mode.
    with os.fdopen(fd, "w") as f:
        f.write(token)


def load_token() -> str | None:
    try:
        return token_path().read_text().strip() or None
    except FileNotFoundError:
        return None


def delete_token() -> bool:
    try:
        token_path().unlink()
    except FileNotFoundError:
        return False
    return True
