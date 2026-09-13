"""Query filters for ``GET /files`` and their SQLAlchemy clause builder.

See docs/design/db.md and docs/design/api.md for the field list and the
categorical (exact-match, OR-within-field) vs. scalar (range-bound) split.
"""

from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy import Select, select

from server.db.files import File

DEFAULT_LIMIT = 100
MAX_LIMIT = 500


class FileListFilters(BaseModel):
    """Filters accepted by ``GET /files``, mapped from query params."""

    name: list[str] | None = None
    channels: list[int] | None = None
    sample_format: list[str] | None = None
    codec: list[str] | None = None
    sample_rate: list[int] | None = None

    min_duration: float | None = None
    max_duration: float | None = None
    min_created_at: datetime | None = None
    max_created_at: datetime | None = None

    limit: int = Field(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)
    offset: int = Field(default=0, ge=0)


def build_file_query(filters: FileListFilters) -> Select:
    """Build a ``SELECT`` over ``File`` with filters applied.

    Pagination (``limit``/``offset``) is intentionally not applied here —
    the same filtered query is reused for both the paginated row fetch and
    the separate ``total`` count, per docs/design/db.md.
    """
    query = select(File)

    if filters.name is not None:
        query = query.where(File.name.in_(filters.name))
    if filters.channels is not None:
        query = query.where(File.channels.in_(filters.channels))
    if filters.sample_format is not None:
        query = query.where(File.sample_format.in_(filters.sample_format))
    if filters.codec is not None:
        query = query.where(File.codec.in_(filters.codec))
    if filters.sample_rate is not None:
        query = query.where(File.sample_rate.in_(filters.sample_rate))

    if filters.min_duration is not None:
        query = query.where(File.duration_seconds >= filters.min_duration)
    if filters.max_duration is not None:
        query = query.where(File.duration_seconds <= filters.max_duration)
    if filters.min_created_at is not None:
        query = query.where(File.created_at >= filters.min_created_at)
    if filters.max_created_at is not None:
        query = query.where(File.created_at <= filters.max_created_at)

    return query
