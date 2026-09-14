"""Application settings loaded from the environment and .env file."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the audio file server.

    Fields are read from environment variables prefixed with
    ``AUDIO_SERVER_`` (or from a local .env file), which keeps them from
    colliding with unrelated services sharing this machine.
    """

    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        env_prefix="AUDIO_SERVER_",
    )

    app_name: str = "audio-server"
    app_version: str = "0.1.0"
    debug: bool = False

    port: int = 8000
    frontend_port: int = 3000

    allowed_methods: list[str] = ["GET", "POST", "PATCH", "DELETE", "OPTIONS"]
    allowed_headers: list[str] = ["Authorization", "Content-Type"]
    allow_credentials: bool = True

    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket_name: str = "audio-files"
    s3_region: str = "us-east-1"

    db_host: str = "localhost"
    db_port: int = 5432
    db_user: SecretStr
    db_password: SecretStr
    db_name: str = "audio-server-db"

    @property
    def allowed_origins(self) -> list[str]:
        """Origin the frontend is expected to run on, derived from its port."""
        return [f"http://localhost:{self.frontend_port}"]


settings = Settings()
