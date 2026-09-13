"""Integration tests for upload rejection paths end to end.

See docs/design/testing.md: rejections must leave no object and no row
behind, and a duplicate name must be caught by the real Postgres unique
constraint, not just an application-level check.
"""

import pytest
from botocore.exceptions import ClientError
from sqlalchemy import select

from server.config import settings
from server.db.files import File
from tests.helpers import make_non_wav_bytes, make_wav_bytes


def test_non_wav_upload_leaves_no_object_or_row(client, s3_client, db_session):
    name = "rejected-upload.wav"

    response = client.post(f"/files?name={name}", content=make_non_wav_bytes())

    assert response.status_code == 415

    row = db_session.scalar(select(File).where(File.name == name))
    assert row is None

    with pytest.raises(ClientError):
        s3_client.head_object(Bucket=settings.s3_bucket_name, Key=name)


def test_duplicate_name_is_rejected_with_409(client):
    name = "duplicate-name-test.wav"
    wav_bytes = make_wav_bytes()

    first = client.post(f"/files?name={name}", content=wav_bytes)
    assert first.status_code == 201

    second = client.post(f"/files?name={name}", content=wav_bytes)
    assert second.status_code == 409
