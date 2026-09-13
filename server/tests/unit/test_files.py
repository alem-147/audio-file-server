"""Unit tests for server.files — upload name assignment.

No DB/S3/network; see docs/design/testing.md.
"""

import re

from server.files import assign_upload_name

_GENERATED_NAME_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.wav$"
)


def test_explicit_name_is_used_as_is():
    assert assign_upload_name("clip.wav") == "clip.wav"


def test_omitted_name_generates_a_uuid_wav_filename():
    name = assign_upload_name(None)

    assert _GENERATED_NAME_PATTERN.match(name)


def test_omitted_name_generates_unique_names():
    first = assign_upload_name(None)
    second = assign_upload_name(None)

    assert first != second
