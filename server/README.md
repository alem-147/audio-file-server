# server

## Running tests

```
uv run pytest tests/unit          # fast, no infra required
uv run pytest tests/integration   # spins up Postgres + MinIO via testcontainers; requires Docker
```

On Rancher Desktop, the integration suite's cleanup container ("Ryuk")
fails to start (it tries to bind-mount a socket path Rancher Desktop
doesn't support). Work around it with:

```
TESTCONTAINERS_RYUK_DISABLED=true uv run pytest tests/integration
```
