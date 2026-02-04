from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import quote_plus


def _build_database_url() -> str:
    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        return env_url

    pg_user = os.environ.get("PGUSER", "postgres")
    pg_password = os.environ.get("PGPASSWORD", "12345")
    pg_host = os.environ.get("PGHOST", "localhost")
    pg_port = os.environ.get("PGPORT", "5432")
    pg_db = os.environ.get("PGDATABASE", "dejurka")
    return (
        f"postgresql://{pg_user}:{quote_plus(pg_password)}@{pg_host}:{pg_port}/{pg_db}"
    )


@dataclass(frozen=True)
class Settings:
    # Database
    DATABASE_URL: str = _build_database_url()

    # Auth
    JWT_SECRET: str = os.environ.get("JWT_SECRET", "change-me")
    JWT_EXPIRES_IN: str = os.environ.get("JWT_EXPIRES_IN", "7d")

    # OpenAI
    OPENAI_API_KEY: str | None = os.environ.get("OPENAI_API_KEY")
    OPENAI_MODEL: str = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    # External API
    LOCOMOTIVE_API_URL: str | None = os.environ.get("LOCOMOTIVE_API_URL")


settings = Settings()
