# AGENTS.md

Guidance for coding agents working in this repo. See `README.md` for
human-facing setup/usage instructions — this file doesn't restate them.

## Layout

- `server/` — FastAPI API, managed with `uv`. Package source is
  `server/src/server/`.
- `gui/` — frontend, not yet started.
- `docs/design/` — design-decision log. Check here before assuming a design
  choice (storage backend, bucket provisioning, etc.) hasn't already been
  made and reasoned through. Add a new file here for any non-obvious
  architectural decision; don't let decisions live only in commit messages
  or chat history.
- `docker-compose.yml` — MinIO + API, the primary way to run the stack.

## Commands

- Run the full stack: `docker compose up --build`
- Install/sync server deps: `cd server && uv sync`
- Run the server directly: `cd server && uv run <server-command>`
- Tests: `cd server && uv run pytest`
- After changing `server/pyproject.toml`, re-run `uv sync` to update
  `server/uv.lock` before committing.

## Conventions

- Python code follows the Google Python Style Guide (docstrings, typing on
  public APIs, small focused functions, no bare `except`).
- Settings are centralized in `server/src/server/config.py` via
  `pydantic-settings`, env-prefixed with `AUDIO_SERVER_` to avoid colliding
  with other services' generic env vars on a shared machine. Add new
  configuration there rather than reading `os.environ` directly.
- Infra design decisions (storage backend, bucket provisioning, open gaps
  around concurrency/scale and data integrity) live in `docs/design/infra.md`.
  Read it before making assumptions in that area, and add to it rather than
  letting new decisions live only in commit messages or chat history.
