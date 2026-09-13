"""Test-session environment bootstrap.

``server.config`` builds a module-level ``Settings()`` on import, and
``db_user``/``db_password`` have no defaults (they're expected to come from
a local ``.env`` or the deployment environment). ``setdefault`` here means
a developer's real local values still win if a ``.env`` is present; this
only fills the gap so ``import server.config`` succeeds in a bare test
environment, before pytest's per-test ``monkeypatch`` fixture is even
available to help.
"""

import os

os.environ.setdefault("AUDIO_SERVER_DB_USER", "test-user")
os.environ.setdefault("AUDIO_SERVER_DB_PASSWORD", "test-password")
