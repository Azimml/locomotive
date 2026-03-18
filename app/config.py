from __future__ import annotations

import os
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings


def _default_db_url() -> str:
    pg_user = os.environ.get("PGUSER", "postgres")
    pg_password = os.environ.get("PGPASSWORD", "12345")
    pg_host = os.environ.get("PGHOST", "localhost")
    pg_port = os.environ.get("PGPORT", "5432")
    pg_db = os.environ.get("PGDATABASE", "dejurka")
    return f"postgresql://{pg_user}:{quote_plus(pg_password)}@{pg_host}:{pg_port}/{pg_db}"


def _env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return default


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = _default_db_url()

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # ChromaDB / RAG
    CHROMA_PERSIST_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "chroma_db")
    CHROMA_COLLECTION: str = "repair_manuals"
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Brigade external API (DasUtyAI)
    BRIGADE_API_URL: str = _env("DASUTY_API_URL", default="https://emm.railway.uz/api")
    BRIGADE_API_CLIENT_ID: str = _env("DASUTY_API_CLIENT_ID", default="Sunnat_20erw26ff")
    BRIGADE_API_CLIENT_SECRET: str = _env("DASUTY_API_CLIENT_SECRET", default="y7b23234@d84f")
    BRIGADE_DATA_CACHE_PATH: str = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "cache",
        "dataset.json",
    )
    # Chainlit
    CHAINLIT_AUTH_SECRET: str = "change-me-chainlit-secret"
    CHAINLIT_AUTH_USERNAME: str = "admin"
    CHAINLIT_AUTH_PASSWORD: str = "admin"
    CHAINLIT_AUTH_FULL_NAME: str = "Chainlit Admin"
    CHAINLIT_PERSISTENCE_ENABLED: bool = True
    CHAINLIT_DB_SCHEMA: str = "chainlit"

    # CORS
    CORS_ORIGINS: tuple[str, ...] = ("*",)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
