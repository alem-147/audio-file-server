# audio-file-server
A small HTTP API for uploading, storing, listing, downloading, and inspecting audio files.

Audio files are stored in an S3-compatible object store ([MinIO](https://min.io/)
locally; real AWS S3 in production). See
[`docs/design/infra.md`](docs/design/infra.md) for the reasoning behind that
and other infra decisions.

## Run (Docker Compose)

Brings up the API and its MinIO backing store together:

```bash
docker compose up --build
```

The API will be available at `http://localhost:8000` (override with
`AUDIO_SERVER_PORT` in a root `.env` file if that port is already in use on
your machine). The MinIO console is at `http://localhost:9001`
(`minioadmin` / `minioadmin` by default).

## Local development (without Docker)

Run MinIO via Compose, then run the API directly for faster iteration:

```bash
docker compose up minio postgres
cp .env.example .env   # point AUDIO_SERVER_S3_ENDPOINT_URL/AUDIO_SERVER_DB_HOST at localhost
cd server
uv sync
uv run <server-command>
```

## API

### Upload

```bash
curl -X POST \
  --data-binary @myfile.wav \
  http://localhost:8000/files
```

### List

```bash
curl http://localhost:8000/files
```

### Download

```bash
curl http://localhost:8000/files/myfile.wav
```

### Metadata

```bash
curl http://localhost:8000/files/myfile.wav/info
```

### Filter by duration

```bash
curl "http://localhost:8000/files?maxduration=300"
```

## Tests

```bash
cd server
uv run pytest
```

