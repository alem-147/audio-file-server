"""Integration test for the object-then-metadata write ordering.

See docs/design/api.md's Consistency section: if the metadata row write
fails after the object write already succeeded, the object is left in
place rather than rolled back — an orphaned object is an acceptable
failure mode, an orphaned row (or a lost object) is not.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from server.config import settings
from server.db.files import File
from tests.helpers import make_wav_bytes


def test_object_survives_simulated_metadata_write_failure(
    client, s3_client, db_session, monkeypatch
):
    def failing_commit(self):
        raise RuntimeError("simulated metadata write failure")

    monkeypatch.setattr(Session, "commit", failing_commit)

    name = "consistency-ordering-test.wav"
    with pytest.raises(RuntimeError):
        client.post(f"/files?name={name}", content=make_wav_bytes())

    head_response = s3_client.head_object(
        Bucket=settings.s3_bucket_name, Key=name
    )
    assert head_response["ResponseMetadata"]["HTTPStatusCode"] == 200

    row = db_session.scalar(select(File).where(File.name == name))
    assert row is None
