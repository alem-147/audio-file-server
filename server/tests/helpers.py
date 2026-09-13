"""Helpers for building synthetic WAV byte streams for tests.

Precise control over sample counts and header fields matters more than
realism here — see docs/design/testing.md for why these are generated
in-test rather than read from ``fixtures/*.wav``.
"""

import io
import struct
import wave


def make_wav_bytes(
    *,
    channels: int = 1,
    sample_rate: int = 8000,
    bit_depth: int = 16,
    num_samples: int = 8000,
) -> bytes:
    """Build a minimal valid PCM WAV file containing silence."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(bit_depth // 8)
        writer.setframerate(sample_rate)
        frame = b"\x00" * (bit_depth // 8) * channels
        writer.writeframes(frame * num_samples)
    return buffer.getvalue()


def make_non_wav_bytes() -> bytes:
    """Bytes that aren't a WAV file, or any recognizable audio format."""
    return b"this is plainly not a wav file\n" * 4


def make_truncated_wav_bytes() -> bytes:
    """A WAV file with a complete, valid header but far less sample data
    than the header's ``data`` chunk size declares — as if a transfer was
    cut off partway through. ``wave.open`` doesn't validate this on its
    own since it trusts the declared chunk size, not the actual byte
    count, so this exercises the frame-count check in ``parse_wav``.
    """
    full = make_wav_bytes(num_samples=8000)
    return full[:100]


def make_float_wav_bytes(
    *,
    channels: int = 1,
    sample_rate: int = 8000,
    num_samples: int = 8000,
) -> bytes:
    """A WAV file with an IEEE-float ``fmt`` tag (3), which ``wave`` rejects.

    Built by hand, since the stdlib ``wave`` module only ever writes PCM
    (tag 1) and has no API for producing a float-tagged file.
    """
    bit_depth = 32
    block_align = channels * bit_depth // 8
    byte_rate = sample_rate * block_align
    data = b"\x00" * (bit_depth // 8) * channels * num_samples

    fmt_chunk = struct.pack(
        "<HHIIHH",
        3,  # audio format: IEEE float
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bit_depth,
    )
    riff_body = (
        b"WAVE"
        + b"fmt " + struct.pack("<I", len(fmt_chunk)) + fmt_chunk
        + b"data" + struct.pack("<I", len(data)) + data
    )
    return b"RIFF" + struct.pack("<I", len(riff_body)) + riff_body
