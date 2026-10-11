# Mission Control

Mission Control finds qualified and available crew members for a mission.
It is a multi-tenant FastAPI API with a Typer CLI (`mc`), on Postgres, in a uv workspace (Python 3.12).
Read `design/DESIGN.md` before you change the data model, the API or the CLI.

## Commands

- `verify:fast`: `.claude/hooks/verify.sh fast`
- `verify:full`: `.claude/hooks/verify.sh full`
- All tests: `uv run pytest`
- Selected tests: `uv run pytest -k <filter>`
- Build: none. The packages run from the workspace with `uv run`.
- Run locally: `docker compose up -d && uv run alembic upgrade head && uv run uvicorn mc_api.main:app --reload`
- CLI: `uv run mc --help`
- New migration: `uv run alembic revision --autogenerate -m "<message>"`

## Conventions

- Put request and response types in `packages/shared` (`mc_shared`). It depends only on Pydantic. The API and the CLI import it.
- Send each tenant query through the org-scoped data-access layer. Look up each referenced ID with an org filter.
- Give each tenant table `org_id NOT NULL`. Give parent tables `UNIQUE(org_id, id)`. Child tables use composite foreign keys `(org_id, x_id)`.
- Use a UUID `id` primary key and `created_at` and `updated_at` on each table.
- Return 404 for a resource in another org. Return 403 with the role and the rule for a forbidden action in the own org.
- Add cross-org access checks to the happy path tests of each build step.

## Git

- Make one commit for each slice or piece of work. Before a push, amend that commit.
- Write the commit subject as what the commit adds. Write the body as what and why, not how.
- To change a pushed commit that is not merged, use `git commit --fixup <sha>`, then `GIT_SEQUENCE_EDITOR=: git rebase -i --autosquash develop`.
- PRs merge on GitHub with "Rebase and merge". Before you create a branch or rebase, update `develop`: `git fetch origin develop:develop`, or `git pull --ff-only origin develop` when `develop` is checked out.
- Rebase a branch onto `develop`. Do not merge `develop` into a branch.
- Do not force-push. After you rewrite a pushed branch, tell the user to run `git push --force-with-lease`.

## Gotchas

- The tests need Postgres. Run `docker compose up -d` before `uv run pytest`.
- Alembic runs from the repo root. `alembic.ini` points to `packages/api/alembic`.
- The API reads `DATABASE_URL` and the CLI reads `MC_API_URL`. The defaults match `docker-compose.yml`.
- `BRIEF.md` is the challenge brief. Do not edit it.

## Compaction

Keep: the current task, the build step from `design/DESIGN.md`, the files changed, the open questions.
