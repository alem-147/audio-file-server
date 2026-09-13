"""SQLAlchemy engine and session factory for the app's runtime queries."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from server.config import Settings


def build_database_url(settings: Settings) -> str:
    """Build a psycopg2 SQLAlchemy URL from application settings."""
    user = settings.db_user.get_secret_value()
    password = settings.db_password.get_secret_value()
    return (
        f"postgresql+psycopg2://{user}:{password}@"
        f"{settings.db_host}:{settings.db_port}/{settings.db_name}"
    )


def create_session_factory(settings: Settings) -> sessionmaker:
    """Build a sessionmaker bound to an engine built from `settings`."""
    engine = create_engine(build_database_url(settings))
    return sessionmaker(bind=engine, expire_on_commit=False)
