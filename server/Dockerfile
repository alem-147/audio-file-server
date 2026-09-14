FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations
COPY entrypoint.sh ./

RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["./entrypoint.sh"]
