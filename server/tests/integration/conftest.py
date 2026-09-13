"""Session-scoped Postgres + MinIO containers for integration tests.

Ephemeral, spun up via testcontainers-python, with no dependency on
`docker compose up` already running — see docs/design/testing.md.
"""

import time

import boto3
import psycopg2
import pytest
from alembic import command
from alembic.config import Config
from botocore.client import Config as BotoConfig
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.community.postgres import PostgresContainer
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import LogMessageWaitStrategy

from server.config import settings
from server.main import create_app
from server.routes import get_db_session, get_s3_client

_MINIO_PORT = 9000
_MINIO_ACCESS_KEY = "minioadmin"
_MINIO_SECRET_KEY = "minioadmin"
_POSTGRES_READY_TIMEOUT_SECONDS = 30


def _wait_until_postgres_accepts_connections(container):
    """Poll with a real connection attempt until Postgres is ready.

    `PostgresContainer`'s own readiness wait has been observed to return
    before the server inside the container is actually accepting TCP
    connections (a startup race, not something this test suite can fix
    upstream), so this polls the actual protocol the app will use instead
    of trusting the container's own "started" signal.
    """
    dsn = container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql://"
    )
    deadline = time.monotonic() + _POSTGRES_READY_TIMEOUT_SECONDS
    last_error = None
    while time.monotonic() < deadline:
        try:
            psycopg2.connect(dsn).close()
            return
        except psycopg2.OperationalError as exc:
            last_error = exc
            time.sleep(0.5)
    raise RuntimeError("Postgres test container never became ready") from last_error


@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16-alpine") as container:
        _wait_until_postgres_accepts_connections(container)
        yield container


@pytest.fixture(scope="session")
def minio_container():
    container = (
        DockerContainer("quay.io/minio/minio:latest")
        .with_exposed_ports(_MINIO_PORT)
        .with_env("MINIO_ROOT_USER", _MINIO_ACCESS_KEY)
        .with_env("MINIO_ROOT_PASSWORD", _MINIO_SECRET_KEY)
        .with_command("server /data")
        .waiting_for(LogMessageWaitStrategy("API:"))
    )
    with container:
        yield container


@pytest.fixture(scope="session")
def migrated_db_url(postgres_container):
    """Run real Alembic migrations against the container, return its URL.

    Exercises the actual migration files, not just `Base.metadata.create_all`,
    so drift between hand-written migrations and the ORM models would show
    up here too (see the migration smoke test below).
    """
    url = postgres_container.get_connection_url()
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(alembic_cfg, "head")
    return url


@pytest.fixture(scope="session")
def engine(migrated_db_url):
    return create_engine(migrated_db_url)


@pytest.fixture(scope="session")
def session_factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def db_session(session_factory):
    """A session-per-test, so each test's writes are isolated by rollback."""
    session = session_factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="session")
def s3_client(minio_container):
    host = minio_container.get_container_host_ip()
    port = minio_container.get_exposed_port(_MINIO_PORT)
    client = boto3.client(
        "s3",
        endpoint_url=f"http://{host}:{port}",
        aws_access_key_id=_MINIO_ACCESS_KEY,
        aws_secret_access_key=_MINIO_SECRET_KEY,
        region_name="us-east-1",
        config=BotoConfig(signature_version="s3v4"),
    )
    client.create_bucket(Bucket=settings.s3_bucket_name)
    return client


@pytest.fixture
def client(session_factory, s3_client):
    """A TestClient with DB/S3 dependencies overridden to point at the
    containers above, instead of running the app's real lifespan (which
    would otherwise try to reach the real dev endpoints in `settings`).
    """

    def override_get_db_session():
        with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_s3_client] = lambda: s3_client
    return TestClient(app)
