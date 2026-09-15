# Runbook: exercising the API by hand

Manual `curl` recipes for every endpoint, against a locally running stack.
For the route contract and the reasoning behind it, see `docs/design/api.md`.

## Start the stack

```bash
docker compose up -d
```

Waits on Postgres/MinIO health checks, runs migrations, then starts the
server on `http://localhost:8000`. Confirm it's up:

```bash
curl -s http://localhost:8000/files
```

`fixtures/*.wav` (six short clips) are handy test payloads — commands below
use `fixtures/funk.wav` as a stand-in; swap in any of the others.

## POST /files — upload

Auto-named (server generates a `<uuid>.wav` name):

```bash
curl -s -X POST --data-binary @fixtures/funk.wav http://localhost:8000/files
```

Explicit name:

```bash
curl -s -X POST --data-binary @fixtures/funk.wav "http://localhost:8000/files?name=funk.wav"
```

Expect `201` with the parsed metadata (`name`, `size_bytes`,
`duration_seconds`, `sample_rate`, `channels`, `bit_depth`, `codec`,
`sample_format`, `created_at`). Print the status code alongside the body
for any of these with `-w`:

```bash
curl -s -w "\nstatus: %{http_code}\n" -X POST --data-binary @fixtures/funk.wav "http://localhost:8000/files?name=funk.wav"
```

**Rejection cases** — worth checking these actually fail, not just the
happy path:

```bash
# non-WAV body -> 415, no object or row left behind
echo "not audio" | curl -s -o /dev/null -w "%{http_code}\n" -X POST --data-binary @- http://localhost:8000/files

# duplicate name -> 409
curl -s -X POST --data-binary @fixtures/funk.wav "http://localhost:8000/files?name=dup.wav" > /dev/null
curl -s -o /dev/null -w "%{http_code}\n" -X POST --data-binary @fixtures/funk.wav "http://localhost:8000/files?name=dup.wav"
```

## GET /files — list

Light listing (default — just `name` + `duration_seconds`):

```bash
curl -s http://localhost:8000/files | python3 -m json.tool
```

Full listing (same shape as `GET /files/{name}/info`, per row):

```bash
curl -s "http://localhost:8000/files?fields=full" | python3 -m json.tool
```

Filters — categorical (repeatable, OR within a field, AND across fields)
and scalar (`min_`/`max_` range pairs):

```bash
curl -s "http://localhost:8000/files?channels=1&channels=2"        # mono OR stereo
curl -s "http://localhost:8000/files?sample_rate=44100&codec=PCM"  # AND across fields
curl -s "http://localhost:8000/files?min_duration=10&max_duration=300"
curl -s "http://localhost:8000/files?min_created_at=2026-01-01T00:00:00Z"
```

Pagination:

```bash
curl -s "http://localhost:8000/files?limit=2&offset=0"
curl -s "http://localhost:8000/files?limit=2&offset=2"
```

An unrecognized query param fails loudly (`400`) instead of silently
ignoring the typo:

```bash
curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:8000/files?maxDuration=300"
```

## GET /files/{name} — download

```bash
curl -s http://localhost:8000/files/funk.wav -o /tmp/downloaded.wav
diff fixtures/funk.wav /tmp/downloaded.wav && echo "bytes match"
```

Missing name → `404`:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/files/does-not-exist.wav
```

## GET /files/{name}/info — metadata

```bash
curl -s http://localhost:8000/files/funk.wav/info | python3 -m json.tool
```

Same `404` behavior as download for a missing name.

## DELETE /files/{name}

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X DELETE http://localhost:8000/files/funk.wav   # 204
curl -s http://localhost:8000/files | python3 -c "import json,sys; print([f['name'] for f in json.load(sys.stdin)['items']])"  # confirm it's gone
curl -s -o /dev/null -w "%{http_code}\n" -X DELETE http://localhost:8000/files/funk.wav   # 404 the second time
```

## OpenAPI spec

FastAPI serves the live schema and interactive docs — useful for checking
a route's exact contract without reading source, and it's what
`gui/npm run gen:api` consumes to generate frontend types:

```bash
curl -s http://localhost:8000/openapi.json | python3 -m json.tool
```

Interactive Swagger UI: http://localhost:8000/docs

## Resetting to a clean slate

```bash
docker compose down -v   # drops Postgres + MinIO volumes too
docker compose up -d
```
