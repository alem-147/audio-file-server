"""API request/response schemas for file endpoints. See docs/design/api.md.

Kept separate from the `File` ORM model (`server.db.files`), per the
SQLAlchemy-not-SQLModel decision in docs/design/db.md.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FileInfo(BaseModel):
    """Full metadata record, returned by upload and by `GET /files/{name}/info`."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    size_bytes: int
    duration_seconds: float
    sample_rate: int
    channels: int
    bit_depth: int
    codec: str
    sample_format: str
    created_at: datetime


class FileListItem(BaseModel):
    """One entry in the `GET /files` listing: name and duration only."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    duration_seconds: float


class FileListResponse(BaseModel):
    """Pagination envelope for `GET /files`.

    `items` is `FileListItem` by default, or `FileInfo` when the caller
    passes `?fields=full` (see `routes.list_files`).
    """

    items: list[FileListItem] | list[FileInfo]
    total: int
    limit: int
    offset: int
