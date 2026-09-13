"""Integration test: the full POST /files -> object -> row -> GET path.

See docs/design/testing.md.
"""

from sqlalchemy import select

from server.config import settings
from server.db.files import File
from tests.helpers import make_wav_bytes


def test_upload_round_trip(client, s3_client, db_session):
    wav_bytes = make_wav_bytes(
        channels=2, sample_rate=16000, num_samples=32000
    )
    name = "round-trip-test.wav"

    response = client.post(f"/files?name={name}", content=wav_bytes)

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == name
    assert body["duration_seconds"] == 2.0
    assert body["channels"] == 2
    assert body["sample_rate"] == 16000
    assert body["codec"] == "PCM"

    obj = s3_client.get_object(Bucket=settings.s3_bucket_name, Key=name)
    assert obj["Body"].read() == wav_bytes

    row = db_session.scalar(select(File).where(File.name == name))
    assert row is not None
    assert row.duration_seconds == 2.0
    assert row.size_bytes == len(wav_bytes)

    download = client.get(f"/files/{name}")
    assert download.status_code == 200
    assert download.content == wav_bytes
    assert download.headers["content-type"] == "audio/wav"

    info = client.get(f"/files/{name}/info")
    assert info.status_code == 200
    assert info.json()["name"] == name
    assert info.json()["duration_seconds"] == 2.0
