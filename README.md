# Mission Control

Mission Control finds qualified and available crew members for a mission. It is a multi-tenant API with a CLI (`mc`).

- Design: [design/DESIGN.md](design/DESIGN.md)
- Challenge brief: [BRIEF.md](BRIEF.md)

## Prerequisites
- Docker with Compose
- [uv](https://docs.astral.sh/uv/). uv installs Python 3.12 if necessary.

## Run locally
```sh
docker compose up -d                       # Postgres on localhost:5432
uv sync                                    # install the workspace into .venv
uv run alembic upgrade head                # apply DB migrations
uv run uvicorn mc_api.main:app --reload    # API on http://localhost:8000
```

In a second terminal:
```sh
uv run mc health                           # API ok, database ok
uv run mc --help
```

The API docs are at http://localhost:8000/docs.

## Test
Postgres must run (`docker compose up -d`).
```sh
uv run pytest
```

## Configuration
The defaults match `docker-compose.yml`, so the run steps need no configuration. To override a value, copy `.env.example` to `.env`, edit it and load it with `uv run --env-file .env <command>`.

| Variable | Default | Used by |
|----------|---------|---------|
| `DATABASE_URL` | `postgresql+psycopg://mc:mc@localhost:5432/mc` | API, Alembic |
| `MC_API_URL` | `http://localhost:8000` | CLI |

## Repository layout
| Path | Content |
|------|---------|
| `packages/shared` | `mc_shared`: request and response types. Depends only on Pydantic. The API and the CLI import it. |
| `packages/api` | `mc_api`: FastAPI app, SQLAlchemy, Alembic migrations (`packages/api/alembic`), tests |
| `packages/cli` | `mc_cli`: Typer CLI, entry point `mc` |
| `design/` | Design document and decisions |
