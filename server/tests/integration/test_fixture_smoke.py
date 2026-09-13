"""End-to-end smoke test against the real fixture WAV files in /fixtures.

The rest of the integration suite deliberately uses synthetic WAV bytes
for precise control over edge cases (see docs/design/testing.md). This
test instead exercises upload -> list -> download against real audio
files, as a sanity check that nothing about actual (non-synthetic) WAV
encoding trips up the parser or the storage round trip.
"""

import hashlib
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_upload_two_files_list_and_download_one_matches_checksum(client):
    fixtures = {
        "fixture-funk.wav": (FIXTURES_DIR / "funk.wav").read_bytes(),
        "fixture-lofi.wav": (FIXTURES_DIR / "lofi.wav").read_bytes(),
    }

    for stored_name, data in fixtures.items():
        response = client.post(f"/files?name={stored_name}", content=data)
        assert response.status_code == 201, response.text

    list_response = client.get("/files", params={"limit": 500})
    assert list_response.status_code == 200
    listed_names = {item["name"] for item in list_response.json()["items"]}
    assert set(fixtures) <= listed_names

    name, original_bytes = next(iter(fixtures.items()))
    download = client.get(f"/files/{name}")

    assert download.status_code == 200
    assert download.headers["content-type"] == "audio/wav"
    assert len(download.content) == len(original_bytes)
    assert _sha256(download.content) == _sha256(original_bytes)
