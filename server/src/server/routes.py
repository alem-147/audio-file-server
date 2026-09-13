"""HTTP routes for file upload, download, listing, and metadata.

See docs/design/api.md for the contract these implement.
"""

from datetime import datetime
from typing import Annotated

from botocore.client import BaseClient
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from server.audio import InvalidAudioError, parse_wav
from server.config import settings
from server.db.files import File
from server.db.filters import FileListFilters, build_file_query
from server.files import assign_upload_name
from server.schemas import FileInfo, FileListItem, FileListResponse

router = APIRouter()

_KNOWN_LIST_FILES_PARAMS = {
    "name",
    "channels",
    "sample_format",
    "codec",
    "sample_rate",
    "min_duration",
    "max_duration",
    "min_created_at",
    "max_created_at",
    "limit",
    "offset",
}


def get_db_session(request: Request) -> Session:
    """Yield a request-scoped session from the app's session factory."""
    session_factory = request.app.state.db_session_factory
    with session_factory() as session:
        yield session


def get_s3_client(request: Request) -> BaseClient:
    """Return the app-wide S3 client set up in the lifespan hook."""
    return request.app.state.s3_client


def reject_unknown_query_params(request: Request) -> None:
    """Reject a `GET /files` call with an unrecognized filter param.

    A typo'd filter (`?maxDuration=`) fails loudly with a 400 instead of
    silently returning an unfiltered list, per docs/design/api.md.
    """
    unknown = set(request.query_params.keys()) - _KNOWN_LIST_FILES_PARAMS
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"unrecognized query parameter(s): {sorted(unknown)}",
        )


@router.post("/files", response_model=FileInfo, status_code=201)
async def upload_file(
    request: Request,
    db: Annotated[Session, Depends(get_db_session)],
    s3_client: Annotated[BaseClient, Depends(get_s3_client)],
    name: str | None = None,
) -> FileInfo:
    """Upload raw WAV bytes, storing the object then the metadata row."""
    body = await request.body()

    try:
        metadata = parse_wav(body)
    except InvalidAudioError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc

    stored_name = assign_upload_name(name)

    s3_client.put_object(
        Bucket=settings.s3_bucket_name, Key=stored_name, Body=body
    )

    file_row = File(
        name=stored_name,
        size_bytes=len(body),
        duration_seconds=metadata.duration_seconds,
        sample_rate=metadata.sample_rate,
        channels=metadata.channels,
        bit_depth=metadata.bit_depth,
        codec=metadata.codec,
        sample_format=metadata.sample_format,
    )
    db.add(file_row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail=f"name already exists: {stored_name}"
        ) from exc

    db.refresh(file_row)
    return FileInfo.model_validate(file_row)


@router.get(
    "/files",
    response_model=FileListResponse,
    dependencies=[Depends(reject_unknown_query_params)],
)
def list_files(
    db: Annotated[Session, Depends(get_db_session)],
    name: Annotated[list[str] | None, Query()] = None,
    channels: Annotated[list[int] | None, Query()] = None,
    sample_format: Annotated[list[str] | None, Query()] = None,
    codec: Annotated[list[str] | None, Query()] = None,
    sample_rate: Annotated[list[int] | None, Query()] = None,
    min_duration: float | None = None,
    max_duration: float | None = None,
    min_created_at: datetime | None = None,
    max_created_at: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> FileListResponse:
    """List stored files, filtered and paginated per docs/design/api.md."""
    filters = FileListFilters(
        name=name,
        channels=channels,
        sample_format=sample_format,
        codec=codec,
        sample_rate=sample_rate,
        min_duration=min_duration,
        max_duration=max_duration,
        min_created_at=min_created_at,
        max_created_at=max_created_at,
        limit=limit,
        offset=offset,
    )

    query = build_file_query(filters)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = (
        db.execute(query.limit(filters.limit).offset(filters.offset))
        .scalars()
        .all()
    )

    return FileListResponse(
        items=[FileListItem.model_validate(row) for row in rows],
        total=total,
        limit=filters.limit,
        offset=filters.offset,
    )


@router.get("/files/{name}")
def download_file(
    name: str,
    db: Annotated[Session, Depends(get_db_session)],
    s3_client: Annotated[BaseClient, Depends(get_s3_client)],
) -> Response:
    """Stream the stored audio bytes back to the caller."""
    row = db.scalar(select(File).where(File.name == name))
    if row is None:
        raise HTTPException(status_code=404, detail=f"no such file: {name}")

    obj = s3_client.get_object(Bucket=settings.s3_bucket_name, Key=name)
    return Response(content=obj["Body"].read(), media_type="audio/wav")


@router.get("/files/{name}/info", response_model=FileInfo)
def get_file_info(
    name: str, db: Annotated[Session, Depends(get_db_session)]
) -> FileInfo:
    """Return the full metadata record for a stored file."""
    row = db.scalar(select(File).where(File.name == name))
    if row is None:
        raise HTTPException(status_code=404, detail=f"no such file: {name}")
    return FileInfo.model_validate(row)


@router.delete("/files/{name}", status_code=204)
def delete_file(
    name: str,
    db: Annotated[Session, Depends(get_db_session)],
    s3_client: Annotated[BaseClient, Depends(get_s3_client)],
) -> Response:
    """Delete a stored file's metadata row and its object.

    Deletes the row before the object, the reverse of the write order in
    `POST /files` (see docs/design/api.md), so a crash between the two
    leaves an orphaned object rather than a row pointing at a missing one.
    """
    row = db.scalar(select(File).where(File.name == name))
    if row is None:
        raise HTTPException(status_code=404, detail=f"no such file: {name}")

    db.delete(row)
    db.commit()

    s3_client.delete_object(Bucket=settings.s3_bucket_name, Key=name)
    return Response(status_code=204)
