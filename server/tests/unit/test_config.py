"""Unit tests for server.config.Settings.

No DB/S3/network; see docs/design/testing.md.
"""

from server.config import Settings


def _settings(**overrides):
    """Build Settings with the required fields filled in and .env disabled.

    ``db_user``/``db_password`` have no defaults, so every test needs to
    supply them; disabling the .env file keeps these tests from picking up
    whatever a developer's local repo-root .env happens to contain.
    """
    overrides.setdefault("db_user", "test-user")
    overrides.setdefault("db_password", "test-password")
    return Settings(_env_file=None, **overrides)


def test_defaults_when_only_required_fields_given():
    settings = _settings()

    assert settings.app_name == "audio-server"
    assert settings.port == 8000
    assert settings.debug is False
    assert settings.s3_bucket_name == "audio-files"
    assert settings.db_name == "audio-server-db"


def test_env_prefixed_var_overrides_default(monkeypatch):
    monkeypatch.setenv("AUDIO_SERVER_DB_USER", "env-user")
    monkeypatch.setenv("AUDIO_SERVER_DB_PASSWORD", "env-password")
    monkeypatch.setenv("AUDIO_SERVER_PORT", "9001")

    settings = Settings(_env_file=None)

    assert settings.db_user.get_secret_value() == "env-user"
    assert settings.port == 9001


def test_unprefixed_env_var_is_ignored(monkeypatch):
    monkeypatch.setenv("PORT", "1234")

    settings = _settings()

    assert settings.port == 8000


def test_allowed_origins_derives_from_frontend_port():
    settings = _settings(frontend_port=4000)

    assert settings.allowed_origins == ["http://localhost:4000"]
