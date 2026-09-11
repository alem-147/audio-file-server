# audio-file-server
A small HTTP API for uploading, storing, listing, downloading, and inspecting audio files.


## Setup

```bash
uv sync
```

## Run

```bash
uv run <server-command>
```

The API will be available at `http://localhost:8000`.

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
uv run pytest
```

