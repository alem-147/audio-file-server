# Testing strategy

`api.md` and `db.md` are fully specified but nothing is implemented yet —
`server/src/server/main.py` has no routes, there's no ORM model, no Alembic
setup. This doc draws the unit/integration boundary and names concretely
what each layer covers, so that the first test files written have a clear
target instead of ad hoc coverage. The intent is to work test-first from
here: write a test against a decision already recorded in `api.md`/`db.md`,
watch it fail because the code doesn't exist yet, then write just enough
code to make it pass.

## Test data: synthetic WAV bytes, not `fixtures/*.wav`

Decision: both unit and integration tests build WAV bytes in-test, via a
small helper that writes minimal valid (and deliberately invalid) WAV
headers — using the stdlib `wave` module for the valid case, and raw byte
manipulation for malformed cases `wave` can't produce on its own (truncated
files, a non-PCM format tag, non-RIFF magic bytes).

Rationale: the real files under `fixtures/` are useful for manual
exploration but the wrong tool for assertions. A test that wants "a WAV
with exactly 16000 samples at 8kHz mono" needs to know the exact expected
`duration_seconds` (`2.0`) up front; reverse-engineering that from a real
recording is fragile (any change to the fixture file silently changes what
the test asserts) and doesn't let a test cheaply construct the edge cases
that matter most here — a truncated header, an IEEE-float `fmt` tag, a
byte stream that isn't RIFF at all. A generated-bytes helper gives full
control over both the valid case and every rejection path in one place,
with no binary fixture files to keep in sync with the assertions that read
them.

## Unit tests — pure logic, no DB/S3/network

No testcontainers, no network calls, no FastAPI `TestClient` hitting real
infra. These run in milliseconds and are where the bulk of edge-case
coverage belongs, per the TDD ordering below.

- **WAV parsing/validation function** (the `wave`-based parser from
  `api.md`): valid PCM WAV bytes → correct `duration_seconds`,
  `sample_rate`, `channels`, `bit_depth`, `codec` (`"PCM"`), and
  `sample_format` (derived from `bit_depth`, per `db.md`). Non-WAV bytes
  (arbitrary/text bytes) → raises the error the route translates to `415`.
  Non-PCM WAV (IEEE-float `fmt` tag `3`) → same rejection, per the
  codec-narrowing decision in `api.md` — `wave.open` raises `wave.Error` on
  it just like any other unsupported format, so this is really the same
  code path as the non-WAV case, worth a test of its own only because it's
  the one deliberately-considered exclusion the design doc calls out.
  Truncated/corrupt WAV (valid RIFF magic, header cut off mid-`fmt` chunk)
  → rejected, not a crash — this is the case most likely to regress if the
  parser is ever hand-rolled instead of using `wave`.
- **`FileListFilters` construction/validation** (`db.md`): no query params
  → all fields `None`, matching the "unfiltered `SELECT`" case in `db.md`.
  `limit` uses its documented default when omitted and is rejected (or
  clamped, whichever `api.md`'s eventual route decides) at the documented
  cap. Categorical fields (`channels`, `sample_format`, `codec`,
  `sample_rate`, `name`) accept repeated values and produce a list.
  Scalar fields (`min_duration`, `max_duration`, `min_created_at`,
  `max_created_at`) reject non-numeric/non-date input via Pydantic
  coercion failure — this is what becomes a `422` at the route layer, but
  the model-level test doesn't need a running app to assert it.
- **Filter → SQLAlchemy clause builder**: given a `FileListFilters`
  instance, asserts the right clauses land on the built `select()` —
  verified by compiling the statement to a string (or inspecting
  `statement.whereclause`), never by executing it against a real
  connection. That's what keeps this a unit test despite touching
  SQLAlchemy: no engine, no DB. Covers, per the categorical/scalar split
  in `db.md`: all-`None` filters → no `WHERE` clause at all; one
  categorical field set → an `IN` clause; one scalar bound set → a
  `>=`/`<=` comparison; multiple fields set together → clauses `AND`ed,
  not `OR`ed, matching "fields AND together" in `db.md`.
- **Upload name assignment**: explicit `?name=` is passed through
  unchanged, including the `.wav` extension if the caller included one — no
  server-side rewriting. Omitted `name` → generated value matches the
  `<uuid>.wav` shape and two calls without a name produce two different
  values (collision would defeat the point of auto-naming).
- **`Settings`** (`server/src/server/config.py`): env-prefix loading (the
  actual prefix string is whatever's already defined in `config.py` —
  don't hardcode a guessed prefix in the test, read it from the module) and
  default values when no environment variables are set.

## Integration tests — real Postgres + MinIO via testcontainers

Decision: spin up Postgres and MinIO per test session using
**testcontainers-python** (the `testcontainers[postgres]` module for
Postgres, the generic container API for MinIO — no first-party
testcontainers MinIO module exists, so it's a generic container started
from the `minio/minio` image with a health check on its ready endpoint),
not a dependency on `docker compose up` already running.

Rationale: a suite that only passes if the developer remembered to start
Compose first is a suite that silently skips in CI, or gives a confusing
connection-refused failure instead of a clear test failure. Ephemeral,
per-session containers make `pytest` self-contained — same command,
same result, whether run locally or in CI, and no leftover state from a
previous run's Postgres data leaking into the next one.

- **Upload round trip**: `POST /files` with generated valid WAV bytes →
  the object exists in the MinIO bucket under the expected key → a
  metadata row exists in Postgres with the expected parsed fields → `GET
  /files/{name}` returns the same bytes back → `GET /files/{name}/info`
  returns metadata matching what was computed at upload time. This is the
  one test that exercises the full write path end to end; everything else
  in this section is a variation or a rejection.
- **Rejection paths end-to-end**: non-WAV body → `415`, and — this is the
  part a unit test can't verify — no object was written to the bucket and
  no row was written to Postgres, confirming the "validate before any
  storage write" ordering `api.md` specifies. Duplicate `name` → `409`,
  verified against the real unique constraint on `files.name` in Postgres
  (`db.md`), not just an application-level pre-check, since the
  constraint (not the check) is what actually closes the concurrent-upload
  race `db.md` describes.
- **List filtering + pagination**: seed several rows spanning different
  `channels`, `sample_format`, `codec`, `sample_rate`, `duration_seconds`,
  and `created_at` values, then assert `GET /files` for: a categorical
  filter with repeated values (OR within the field, e.g. `channels=1` and
  `channels=2` both returned), a scalar range filter (`min_duration`/
  `max_duration`), a combination of both filter kinds together (AND
  across fields — narrower than either alone), and the pagination envelope
  shape (`items`, `total`, `limit`, `offset`) — specifically that `total`
  reflects the full filtered count rather than `len(items)`, per the
  separate-`count()`-query decision in `db.md`.
- **Alembic migration smoke test**: run `alembic upgrade head` against a
  fresh testcontainers Postgres instance, then assert the resulting schema
  matches what the SQLAlchemy models declare (e.g. via
  `MetaData.reflect()` compared against the models' `Table` objects, or
  Alembic's own `--autogenerate` producing no diff against a clean DB).
  Catches drift between hand-written migration files and ORM model
  definitions before it becomes a runtime error on a fresh environment.
- **Consistency ordering**: simulate the metadata-write failure named in
  `api.md`'s Consistency section (e.g. patch the DB insert to raise after
  the object write has already succeeded) and assert the object is left in
  the bucket while no row exists in Postgres — this is the "orphaned
  object is an acceptable failure mode, an orphaned row is not" ordering
  `api.md` chose, and it's only observable with real object storage and a
  real DB in the loop, not mockable without testing the mock instead of
  the ordering.

## Not covered (explicitly out of scope for this pass)

- **Load/concurrency testing.** Concurrency and scale are still deferred
  design questions in both `infra.md` and `api.md` (see their "not yet
  addressed" / "Concurrency and scale" sections) — there's no designed
  behavior yet to write an assertion against, so a load test here would
  just be asserting on whatever happens to fall out of default settings, not
  on a decision.
- **Cross-checking against real AWS S3.** `infra.md` assumes MinIO's
  S3-API compatibility rather than re-verifying it; this testing pass
  inherits that assumption instead of re-litigating it against real S3.

## TDD ordering

Because nothing is implemented yet, tests should be written and made to
pass in this order, not all at once:

1. **Unit tests for the WAV parser and the filter/clause builder first.**
   These need no infra, run in milliseconds, and cover the two pieces of
   logic dense enough with edge cases (rejection paths, clause
   combinations) that they're worth iterating on in a tight loop before
   anything else exists.
2. **Remaining unit tests** (`FileListFilters` validation, upload naming,
   `Settings`) — small, fast, no ordering dependency between them.
3. **Integration tests against testcontainers**, in the order listed
   above (round trip, then rejections, then filtering/pagination, then
   the migration smoke test, then the consistency-ordering test) — each
   one needs progressively more of the implementation to exist before it
   can even fail meaningfully (the round-trip test needs routes, storage,
   and DB wiring all present before it's a useful red test).
4. **Implementation** happens interleaved with 1–3, not after — each test
   is written, watched to fail, then just enough of
   `server/src/server/` is written to turn it green before moving to the
   next one.

The alternative — writing all tests up front against code that doesn't
exist — would leave a long stretch where every single test is red, with no
signal about which piece of missing implementation to tackle next. Writing
unit tests first also means the fastest-feedback tests are validated
first, so a mistake in the parser or clause builder is caught before it's
built on top of in the integration layer.

## New dev dependency (not installed by this doc)

`testcontainers` (with its `postgres` extra) as a `dev` dependency in
`server/pyproject.toml`, for the integration tests above. Installing it
and wiring up the actual pytest fixtures is implementation work for a
later step — this doc only records that the dependency will be needed and
why.
