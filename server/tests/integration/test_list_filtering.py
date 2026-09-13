"""Integration tests for GET /files filtering and pagination.

See docs/design/testing.md. Sample rates used here are chosen to be
unique to each test so upload data doesn't collide with other integration
test modules sharing the same session-scoped Postgres container.
"""

from tests.helpers import make_wav_bytes


def _upload(client, name, **wav_kwargs):
    response = client.post(
        f"/files?name={name}", content=make_wav_bytes(**wav_kwargs)
    )
    assert response.status_code == 201
    return response.json()


def test_categorical_filter_matches_any_listed_value(client):
    _upload(client, "list-mono.wav", channels=1, sample_rate=47001)
    _upload(client, "list-stereo.wav", channels=2, sample_rate=47001)
    _upload(client, "list-quad.wav", channels=4, sample_rate=47001)

    response = client.get(
        "/files", params=[("sample_rate", 47001), ("channels", 1), ("channels", 2)]
    )

    assert response.status_code == 200
    names = {item["name"] for item in response.json()["items"]}
    assert names == {"list-mono.wav", "list-stereo.wav"}


def test_scalar_range_filter(client):
    rate = 47002
    _upload(client, "list-short.wav", sample_rate=rate, num_samples=rate * 1)
    _upload(client, "list-long.wav", sample_rate=rate, num_samples=rate * 10)

    response = client.get(
        "/files", params={"sample_rate": 47002, "min_duration": 5}
    )

    assert response.status_code == 200
    names = {item["name"] for item in response.json()["items"]}
    assert names == {"list-long.wav"}


def test_combined_filters_narrow_further_than_either_alone(client):
    rate = 47003
    _upload(
        client, "list-combo-match.wav",
        sample_rate=rate, channels=1, num_samples=rate * 10,
    )
    _upload(
        client, "list-combo-wrong-channels.wav",
        sample_rate=rate, channels=2, num_samples=rate * 10,
    )
    _upload(
        client, "list-combo-wrong-duration.wav",
        sample_rate=rate, channels=1, num_samples=rate * 1,
    )

    response = client.get(
        "/files", params={"sample_rate": 47003, "channels": 1, "min_duration": 5}
    )

    names = {item["name"] for item in response.json()["items"]}
    assert names == {"list-combo-match.wav"}


def test_pagination_envelope_total_reflects_full_filtered_count(client):
    for i in range(3):
        _upload(client, f"list-paginated-{i}.wav", sample_rate=47004)

    response = client.get(
        "/files", params={"sample_rate": 47004, "limit": 2, "offset": 0}
    )

    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["limit"] == 2
    assert body["offset"] == 0
