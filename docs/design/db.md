# Database

Metadata for uploaded files (see `api.md`) is persisted in Postgres, queried
via a typed SQLAlchemy ORM, with Alembic managing schema migrations.

## Postgres over SQLite

Decision: Postgres, run as a container alongside MinIO and the API in
Compose, the same way `infra.md` already decided for object storage.

Rationale: SQLite would be less infrastructure to run locally, but this
project already accepted the complexity of a networked backing service
(MinIO) over the simpler local-disk alternative for object storage. Using
SQLite for metadata while MinIO handles bytes would mean two different
complexity budgets for two halves of the same feature, with no real payoff —
this is a single-writer-process app either way. Matching MinIO's level of
complexity keeps the local dev story consistent (`docker compose up`) and
means the metadata store behaves like the production target from day one,
rather than switching engines later and re-discovering Postgres-specific
behavior (constraint enforcement, connection handling) at that point.

## ORM: SQLAlchemy 2.0 + Alembic, not SQLModel

Decision: typed SQLAlchemy 2.0 declarative models (`Mapped[]` /
`mapped_column()`) for the table schema, Alembic for migrations, and
separate Pydantic models for the API request/response schemas.

Rationale:

- This is simple CRUD plus a handful of equality/range filters (duration,
  eventually sample rate). An ORM's query builder covers that cleanly
  without hand-written SQL string assembly, and Alembic's autogenerate
  keeps schema changes reproducible (a migration file per change, not a
  manually-run `ALTER TABLE`).
- SQLModel (same author as FastAPI) merges the table model and the Pydantic
  schema into one class, which is less boilerplate but couples the DB
  schema to the API contract 1:1 — a column added for internal bookkeeping
  would leak into the API response unless carefully excluded, and an API
  field change would pressure the table schema to match. Keeping them
  separate costs one conversion per model
  (`FileInfo.model_validate(row, from_attributes=True)`), which is cheap
  because Pydantic v2 reads attributes off SQLAlchemy row objects directly.
- Reproducible query filters: a Pydantic "filters" model maps onto a
  `select(File).where(...)` built by conditionally appending clauses for
  whichever filter fields are set. That pattern scales to more filters
  without the query-building code growing branchy, and keeps the filter
  *shape* (what a caller can pass) defined in one place, separate from how
  it's translated to SQL. See below for the concrete field list, decided
  alongside `api.md`.

### `FileListFilters`

```python
class FileListFilters(BaseModel):
    # Categorical — exact match, each field ORs its own values, fields AND
    # together. Maps to repeated query params, e.g. ?channels=1&channels=2.
    name: list[str] | None = None
    channels: list[int] | None = None
    sample_format: list[str] | None = None
    codec: list[str] | None = None
    sample_rate: list[int] | None = None

    # Scalar — range bounds, one param pair per field.
    min_duration: float | None = None
    max_duration: float | None = None
    min_created_at: datetime | None = None
    max_created_at: datetime | None = None
```

Categorical fields translate to `File.<field>.in_(values)` clauses; scalar
bounds translate to `File.<field> >= value` / `<= value`. Both kinds are
only appended to the `select()` when the corresponding filter field is not
`None`, so an all-`None` model (no query params supplied) produces an
unfiltered `SELECT`.

Pagination (`limit`/`offset`, see `api.md`) is applied after all filter
clauses via `.limit()`/`.offset()` on the same `select()`, and `total` in
the response envelope comes from a separate `select(func.count()).where(...)`
reusing the same filter clauses — not `len(items)`, since that would just
report the page size back.

## Schema (initial)

Single `files` table — one row per uploaded file, keyed by the same `name`
used in the API's `{name}` path parameter:

| column            | type          | notes                                |
|-------------------|---------------|---------------------------------------|
| `id`              | uuid, PK      | surrogate key, not exposed in the API |
| `name`            | text, unique  | matches the object key in the bucket  |
| `size_bytes`      | bigint        |                                        |
| `duration_seconds`| double        | computed at upload, see `api.md`      |
| `sample_rate`     | integer       |                                        |
| `channels`        | integer       |                                        |
| `bit_depth`       | integer       |                                        |
| `codec`           | text          | always `PCM`, see note below           |
| `sample_format`   | text          | e.g. `int16`, `int32`; derived from `bit_depth` |
| `created_at`      | timestamptz   | default `now()`                       |

`name` is unique and indexed — it's the lookup key for `GET /files/{name}`
and `GET /files/{name}/info`, and the uniqueness constraint is what backs
the `409 Conflict` behavior on duplicate upload names in `api.md`, enforced
by the DB rather than only checked in application code (closes the race
where two concurrent uploads of the same name both pass an application-level
"does this exist" check).

`codec` is a column with exactly one possible value today: `api.md` decided
uploads are parsed with the stdlib `wave` module, which only accepts
PCM-encoded WAV and rejects everything else (IEEE-float, ADPCM, ...) at
`415` before a row is ever written. So `codec` is constant now, not a real
filter dimension. It's still modeled as a column rather than left out,
because the column is what makes adding a second codec later (if `wave` gets
replaced with manual `fmt`-chunk parsing, per the note in `api.md`) a data
migration on existing rows instead of a schema change plus a backfill — the
shape is already there, it just doesn't vary yet. No `CHECK` constraint is
added for the single allowed value, since the upload-time validation in the
API is what actually enforces it; a DB-level constraint would just be a
second place to update the day a second codec is supported.

Not included yet, candidates once the API grows: a checksum column, a
foreign key to a future `datasets` or `speakers` table, soft-delete
(`deleted_at`) instead of hard delete once a `DELETE` endpoint exists.

## Migrations: run at container entrypoint, not app lifespan

Decision: `alembic upgrade head` runs as a step in the server container's
entrypoint, before `uvicorn` starts — not from FastAPI's `lifespan` hook the
way bucket creation is currently handled in `infra.md`.

Rationale: bucket creation is an idempotent existence check safe to run from
every process on every startup, including multiple replicas concurrently.
Schema migrations are a different risk class — running `alembic upgrade
head` from N concurrent API replicas' lifespan hooks races them against each
other on the same migration, which Alembic does not protect against by
default. Running it once, as an explicit entrypoint step ahead of the app
process, keeps "apply schema changes" and "serve traffic" as separate,
ordered steps — the same reasoning `infra.md` used to consider (and reject,
for the simpler bucket case) an init-container pattern; here the migration
risk justifies the extra step where the bucket case didn't.

## Not yet addressed

- Async vs. sync DB driver for the app's runtime queries (`psycopg2-binary`
  is currently in `server/pyproject.toml`; an async app likely wants
  `asyncpg` or `psycopg` 3's async mode instead, with a sync driver kept
  only for Alembic). Deferred until routes are actually implemented against
  the DB.
- Connection pooling behavior under concurrent load — revisit alongside the
  concurrency questions already deferred in `infra.md` and `api.md`.
