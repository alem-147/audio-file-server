"""Unit tests for server.audio — WAV parsing and validation.

No DB/S3/network; see docs/design/testing.md.
"""

import pytest

from server.audio import InvalidAudioError, parse_wav
from tests.helpers import (
    make_float_wav_bytes,
    make_non_wav_bytes,
    make_truncated_wav_bytes,
    make_wav_bytes,
)


def test_parse_valid_pcm_wav_returns_expected_metadata():
    data = make_wav_bytes(
        channels=2, sample_rate=16000, bit_depth=16, num_samples=32000
    )

    metadata = parse_wav(data)

    assert metadata.duration_seconds == 2.0
    assert metadata.sample_rate == 16000
    assert metadata.channels == 2
    assert metadata.bit_depth == 16
    assert metadata.codec == "PCM"
    assert metadata.sample_format == "int16"


def test_parse_non_wav_bytes_raises_invalid_audio_error():
    with pytest.raises(InvalidAudioError):
        parse_wav(make_non_wav_bytes())


def test_parse_non_pcm_wav_raises_invalid_audio_error():
    with pytest.raises(InvalidAudioError):
        parse_wav(make_float_wav_bytes())


def test_parse_truncated_wav_raises_invalid_audio_error_not_crash():
    with pytest.raises(InvalidAudioError):
        parse_wav(make_truncated_wav_bytes())
