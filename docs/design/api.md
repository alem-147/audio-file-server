# API

Formalizes the route shapes sketched in `README.md` into a concrete request/
response contract, and resolves the data-integrity gaps `infra.md` flagged as
"not yet addressed" for this iteration (RIFF validation at upload). Query
filtering, concurrency, and richer metadata (transcripts, speaker ID, dataset
splits) are named as future scope rather than built now — see below.

## Routes

### `POST /files`

Uploads raw audio bytes as the request body (`--data-binary @file.wav`).

- Optional `?name=` query param sets the stored filename. If omitted, the
  server generates one (UUID + `.wav`) and returns it in the response body —
  callers that don't care about naming don't have to invent one.
- `Content-Type` is not trusted for validation; the body is parsed as WAV
  regardless of the declared content type (see Data integrity below).
- Rejects a name collision with `409 Conflict` rather than overwriting.
  Silent overwrite would let one client corrupt another's dataset entry by
  accident; an explicit conflict forces the caller to pick a new name or
  delete first.
- On success, stores the bytes in the object store (`infra.md`) and a
  metadata row in Postgres (`db.md`) in the same request. If metadata
  persistence fails after the object write, the row is what's authoritative
  for "does this file exist" from the API's point of view — see Consistency
  below.
- Response: `201 Created` with the assigned `name` and computed metadata
  (same shape as `GET /files/{name}/info`).

### `GET /files`

Returns a list of stored filenames, optionally filtered.

- Default response stays light — an array of `{name, duration_seconds}`
  entries. `?fields=full` returns the same shape as `GET /files/{name}/info`
  for every row on the page instead.
- Decision: light by default, `full` opt-in. Not because the query is
  cheaper — most fields are already read off the row to satisfy filters
  (`db.md`), so returning them instead of discarding them costs ~nothing
  extra. The real reasons: payload growth as the list scales, and not
  surprising a caller that's paging through the dataset with a
  bigger-than-expected response by default.
- This also covers batch info-fetching: `?name=a&name=b&fields=full` gets
  full records for several known names in one call, reusing the existing
  OR-matched `name` filter (see below) — instead of one
  `GET /files/{name}/info` call per name, or a dedicated batch endpoint.
  A separate batch endpoint was considered and rejected for now: it would
  need its own partial-failure shape (some names found, some not) for a
  need `fields=full` already covers.
- Unrecognized query params are rejected with `400 Bad Request` rather than
  silently ignored, so a typo'd filter (`?maxDuration=`) fails loudly instead
  of returning an unfiltered list.

#### Query filters

Two filter shapes, matching the `FileListFilters` model in `db.md`:

- **Categorical — exact match, repeated params, OR within a field, AND
  across fields**: `name`, `channels`, `sample_format`, `codec`,
  `sample_rate`. Example: `?channels=1&channels=2` returns mono OR stereo
  files; `?channels=1&sample_format=int16` returns mono AND int16 files.
  `sample_rate` is categorical rather than scalar/range: real-world sample
  rates cluster into a small set of standard values (8000, 16000, 44100,
  48000, ...), and "give me files at exactly 16kHz" is the query that
  actually comes up, not "give me files sampled between X and Y." `codec`
  is included even though it's constant-valued today (see `db.md`), so the
  filter shape doesn't need to change the day a second codec is supported.
- **Scalar — range, `min_x`/`max_x` param pairs**: `min_duration`/
  `max_duration` (the prompt's `?maxduration=300` maps to `max_duration`),
  and `min_created_at`/`max_created_at`. Both fields are genuinely
  continuous, unlike sample rate, so a bound makes sense: "clips under 30s"
  or "uploaded after a given date" are real filters, not just a range over
  an otherwise-discrete set of values.

This is deliberately the simplest shape that covers today's fields — one
named param pair per scalar field, rather than a generic operator-suffix
convention (`?duration_lt=30`). The tradeoff: adding a new range-filterable
field later means adding a new named param pair, not just a new field name
plugged into an existing operator vocabulary. Revisit if the number of
scalar fields grows enough that the per-field param pairs become unwieldy.

#### Pagination

`?limit=` and `?offset=` (both optional; `limit` defaults to 100 and is
capped at some max, e.g. 500, to keep a single request bounded). Response
becomes an envelope rather than a bare array, so a caller can tell how many
total matches exist without a separate count request:

```json
{"items": [{"name": "...", "duration_seconds": 12.3}], "total": 842, "limit": 100, "offset": 0}
```

Decision: offset-based, not cursor-based. Cursor pagination (opaque token
encoding a position) is the more correct choice once the underlying data
changes while someone pages through it — offset pagination can skip or
repeat rows if files are inserted or deleted between page fetches. Given
this is currently a single small dataset with no delete endpoint yet and no
concurrent-write scale concerns (per the still-deferred concurrency
section), that failure mode is unlikely enough to not justify cursor
pagination's extra complexity now. Revisit if `DELETE` is added or the
dataset grows large enough that pages are fetched over a long-enough window
for concurrent writes to matter.

`limit`/`offset` apply after the categorical and scalar filters above, not
instead of them — a paginated request is still filtered first, then paged.

### `GET /files/{name}`

Streams the stored audio bytes back to the caller (`Content-Type: audio/wav`).
`404 Not Found` if `name` doesn't exist.

### `GET /files/{name}/info`

Returns the full metadata record as JSON: `name`, `size_bytes`,
`duration_seconds`, `sample_rate`, `channels`, `bit_depth`, `created_at`.
`404 Not Found` if `name` doesn't exist.

### `DELETE /files/{name}`

Deletes one file by name: the metadata row and the object. `204 No Content`
on success, `404 Not Found` if `name` doesn't exist — checked with the same
lookup `GET /files/{name}/info` uses, so a delete of a name nothing lists
behaves the same as any other read of it.

Decision: delete the metadata row first, then the object — the reverse of
the write order `POST /files` uses. Rationale mirrors the Consistency
section below: if a crash happens between the two deletes, the row is
already gone, so the object becomes an orphan invisible to `GET /files` and
`GET /files/{name}/info` (both metadata-DB-driven) rather than a dangling
row whose `GET /files/{name}` now 404s despite still being listed. Same
"orphaned object is harmless, orphaned row is a visible inconsistency"
tradeoff as upload, applied in reverse for the operation that runs in
reverse.

No compensating transaction between the row delete and the object delete,
for the same reason `POST /files` doesn't attempt one: a second failure
mode (a failed compensating delete) to handle for a crash window that's
rare at this scale. An orphaned object left behind by a failed
`s3_client.delete_object` call after the row commit is swept up by the same
future reconciliation job named in the Consistency section, not handled
here.

This closes the gap the pagination section above flagged: offset pagination
was accepted partly on "no delete endpoint yet" — that's no longer true.
The risk (a page skipping or repeating a row because a delete lands between
two page fetches) is still accepted for this scope, since the dataset is
still small enough that this is unlikely to matter in practice; revisit
alongside the rest of that pagination decision if it starts to.

## Data integrity: validating uploads

Decision: parse every uploaded body as a WAV file using Python's stdlib
`wave` module before accepting it. `wave.open` on a non-WAV or truncated
payload raises `wave.Error`, which the handler translates to
`415 Unsupported Media Type`. Metadata (duration, sample rate, channels,
bit depth) is read from the parsed WAV header at upload time, not
recomputed on every GET — see `db.md` for why it's persisted rather than
recomputed.

Rationale:

- Using the stdlib `wave` module instead of hand-rolling RIFF/WAVE chunk
  parsing keeps this small, which matches the "feature-light" scope for
  this iteration — the parsing logic is a few lines, not a new dependency
  or a custom binary parser to maintain and get subtly wrong.
- Consequence of that choice: `wave.open` only understands PCM-encoded WAV
  (`fmt` chunk audio-format tag `1`). It raises `wave.Error` on anything
  else — IEEE-float WAV (tag `3`), ADPCM, etc. — which this API treats as
  a `415`, same as any other non-WAV payload. Decision: accept that
  narrowing deliberately rather than adding manual chunk parsing to
  support other codecs. `codec` is recorded as `PCM` for every file that
  makes it past validation, since that's the only value that's possible
  today; revisit if a non-PCM codec (e.g. float-format audio from an
  upstream pipeline) becomes an actual requirement, at which point the
  parsing needs to move off `wave` to a manual `fmt`-chunk read.
- Validating before any storage write means a rejected upload never
  produces an orphaned object in the bucket or a metadata row for a file
  that doesn't decode. This is what "reject rogue text data" means
  concretely: `curl --data-binary @notes.txt ... /files` gets a `415`, not
  a stored object masquerading as an audio file.
- Trusting the client-supplied `Content-Type` header would defeat the
  point of this check — a client can claim `audio/wav` for anything. The
  header is used only for the outbound `GET /files/{name}` response, never
  for accept/reject decisions on upload.

Explicitly out of scope for this iteration (candidates for later, in
priority order if this becomes a real ingestion pipeline for training
data): checksum/hash stored per file for later corruption detection,
rejecting on sample-rate/channel mismatches against a pipeline's expected
format (currently just recorded, not enforced), and deeper validation than
"does the WAV header parse" — e.g. detecting silence-only or clipped audio,
which matters for training data quality but is a different concern than API
correctness.

## Consistency between object store and metadata DB

Two systems of record (S3/MinIO for bytes, Postgres for metadata) means a
crash between the two writes on `POST /files` is possible. Decision for this
scope: write the object first, then the metadata row; if the row write
fails, the orphaned object is left in place rather than attempting a
compensating delete.

Rationale: a failed delete-after-failed-insert is a second failure mode to
handle for a case (mid-request crash) that's rare at this scale, and an
orphaned object is harmless — it's simply invisible to `GET /files` and
`GET /files/{name}/info` (both are metadata-DB-driven), and can be swept up
by a periodic reconciliation job later. The alternative ordering (metadata
row first, then object) risks the opposite problem: a `GET /files/{name}`
for a row whose object write never landed, which is a more visible
inconsistency (list shows a file that 404s on download) than an orphaned
object nothing lists.

Not yet addressed, revisit if this needs multi-instance durability
guarantees: wrapping both writes in a distributed transaction / outbox
pattern, or a background job to garbage-collect orphaned objects.

## Concurrency and scale

Still deferred, per `infra.md`. Once endpoints exist, add: streaming the
upload body directly to S3 instead of buffering it fully in the handler
(relevant once files are large enough that buffering matters), and moving
WAV parsing off the request path if it becomes a bottleneck under
concurrent uploads.
