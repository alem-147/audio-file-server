"""Upload name assignment for ``POST /files``.

See docs/design/api.md: an explicit ``?name=`` query param is used as-is;
if omitted, the server generates a UUID-based ``.wav`` filename so callers
that don't care about naming don't have to invent one.
"""

import uuid


def assign_upload_name(explicit_name: str | None) -> str:
    """Return the stored filename for an upload.

    Returns ``explicit_name`` unchanged when the caller supplied one.
    Otherwise generates a UUID-based ``.wav`` filename.
    """
    if explicit_name is not None:
        return explicit_name
    return f"{uuid.uuid4()}.wav"
