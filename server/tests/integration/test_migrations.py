"""Alembic migration smoke test.

Runs `alembic upgrade head` against a fresh testcontainers Postgres (via
the `engine` fixture, which depends on `migrated_db_url`) and asserts the
resulting schema matches the SQLAlchemy model — catching drift between
hand-written migration files and the ORM model definition. See
docs/design/testing.md.
"""

from sqlalchemy import inspect

from server.db.files import File


def test_migrated_schema_matches_orm_model(engine):
    inspector = inspect(engine)

    assert "files" in inspector.get_table_names()

    migrated_columns = {col["name"] for col in inspector.get_columns("files")}
    model_columns = {column.name for column in File.__table__.columns}
    assert migrated_columns == model_columns

    indexes = inspector.get_indexes("files")
    assert any(
        idx["column_names"] == ["name"] and idx["unique"] for idx in indexes
    )
