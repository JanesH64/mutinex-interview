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
uv run mc-seed                             # load the demo data
uv run uvicorn mc_api.main:app --reload    # API on http://localhost:8000
```

In a second terminal:
```sh
uv run mc health                           # API ok, database ok
uv run mc --help
```

The API docs are at http://localhost:8000/docs.

## Test
Postgres must run (`docker compose up -d`). The tests use the database `mc_test`. The test run creates it.
```sh
uv run pytest
```

## Seed data
`mc-seed` loads a fixed demo dataset: 2 orgs, 19 users, skills, leave, 4 missions and their assignments.

**Warning:** `mc-seed` deletes all data in the database of `DATABASE_URL`. Use it only on a local demo database.

| Username | Display name | Org | Role |
|----------|--------------|-----|------|
| `diana` | Diana Reyes | Artemis Space Agency | DIRECTOR |
| `dmitri` | Dmitri Volkov | Artemis Space Agency | DIRECTOR |
| `leo` | Leo Hart | Artemis Space Agency | LEAD |
| `lena` | Lena Okafor | Artemis Space Agency | LEAD |
| `ava` | Ava Lindqvist | Artemis Space Agency | CREW |
| `ben` | Ben Carter | Artemis Space Agency | CREW |
| `cara` | Cara Novak | Artemis Space Agency | CREW |
| `dev` | Dev Patel | Artemis Space Agency | CREW |
| `eli` | Eli Moreau | Artemis Space Agency | CREW |
| `fay` | Fay Adeyemi | Artemis Space Agency | CREW |
| `gus` | Gus Brandt | Artemis Space Agency | CREW |
| `hana` | Hana Sato | Artemis Space Agency | CREW |
| `ivan` | Ivan Petrov | Artemis Space Agency | CREW |
| `jo` | Jo Kim | Artemis Space Agency | CREW |
| `nora` | Nora Quinn | Nova Orbital | DIRECTOR |
| `nick` | Nick Alvarez | Nova Orbital | LEAD |
| `nell` | Nell Foster | Nova Orbital | CREW |
| `ned` | Ned Ito | Nova Orbital | CREW |
| `nia` | Nia Banda | Nova Orbital | CREW |

The reference window for the matcher is 2027-01-11 to 2027-01-24 in org Artemis Space Agency.

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
