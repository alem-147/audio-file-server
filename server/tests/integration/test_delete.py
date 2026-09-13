"""Integration tests for DELETE /files/{name}.

See docs/design/api.md: delete removes the metadata row before the object,
and a delete of an unknown name is a 404, same lookup as GET .../info.
"""

import pytest
from botocore.exceptions import ClientError
from sqlalchemy import select

from server.config import settings
from server.db.files import File
from tests.helpers import make_wav_bytes


def test_delete_removes_row_and_object(client, s3_client, db_session):
    name = "delete-round-trip-test.wav"
    wav_bytes = make_wav_bytes()

    upload = client.post(f"/files?name={name}", content=wav_bytes)
    assert upload.status_code == 201

    response = client.delete(f"/files/{name}")
    assert response.status_code == 204

    row = db_session.scalar(select(File).where(File.name == name))
    assert row is None

    with pytest.raises(ClientError):
        s3_client.head_object(Bucket=settings.s3_bucket_name, Key=name)


def test_delete_unknown_name_is_404(client):
    response = client.delete("/files/does-not-exist.wav")
    assert response.status_code == 404


def test_deleted_name_can_be_reused(client):
    name = "delete-then-reupload-test.wav"
    wav_bytes = make_wav_bytes()

    first = client.post(f"/files?name={name}", content=wav_bytes)
    assert first.status_code == 201

    delete = client.delete(f"/files/{name}")
    assert delete.status_code == 204

    second = client.post(f"/files?name={name}", content=wav_bytes)
    assert second.status_code == 201
