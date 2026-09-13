"""WAV parsing and validation for uploaded audio files.

Uses the stdlib ``wave`` module rather than hand-rolled RIFF/WAVE chunk
parsing, per docs/design/api.md. This only accepts PCM-encoded WAV audio;
anything else (IEEE-float, ADPCM, non-WAV bytes, truncated files) raises
``InvalidAudioError``.
"""

import io
import wave
from dataclasses import dataclass

_SAMPLE_FORMATS_BY_BIT_DEPTH = {
    8: "uint8",
    16: "int16",
    32: "int32",
}


class InvalidAudioError(ValueError):
    """Raised when uploaded bytes cannot be parsed as a PCM WAV file."""


@dataclass(frozen=True)
class AudioMetadata:
    """Metadata derived from a parsed WAV file's header."""

    duration_seconds: float
    sample_rate: int
    channels: int
    bit_depth: int
    codec: str
    sample_format: str


def parse_wav(data: bytes) -> AudioMetadata:
    """Parse ``data`` as a PCM WAV file and return its metadata.

    Raises ``InvalidAudioError`` if ``data`` is not a well-formed PCM WAV
    file — non-WAV bytes, a non-PCM format tag such as IEEE-float, or a
    truncated/corrupt header — so the caller can translate it to a 415,
    per docs/design/api.md.
    """
    try:
        with wave.open(io.BytesIO(data), "rb") as reader:
            channels = reader.getnchannels()
            sample_rate = reader.getframerate()
            bit_depth = reader.getsampwidth() * 8
            num_frames = reader.getnframes()
            frame_bytes = reader.readframes(num_frames)
    except (wave.Error, EOFError) as exc:
        raise InvalidAudioError("not a valid PCM WAV file") from exc

    expected_bytes = num_frames * channels * (bit_depth // 8)
    if len(frame_bytes) < expected_bytes:
        raise InvalidAudioError(
            "WAV data is truncated: fewer audio frames than the header declares"
        )

    duration_seconds = num_frames / sample_rate if sample_rate else 0.0
    sample_format = _SAMPLE_FORMATS_BY_BIT_DEPTH.get(
        bit_depth, f"int{bit_depth}"
    )

    return AudioMetadata(
        duration_seconds=duration_seconds,
        sample_rate=sample_rate,
        channels=channels,
        bit_depth=bit_depth,
        codec="PCM",
        sample_format=sample_format,
    )
