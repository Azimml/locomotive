from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import OperationalError

from .config import settings
from .db.base import Base
from .db.session import engine
from .api.chat import router as chat_router
from .api.locomotive import router as locomotive_router
from . import models  # noqa: F401
from chainlit.utils import mount_chainlit


app = FastAPI(title="Locomotive API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    try:
        Base.metadata.create_all(bind=engine)
    except OperationalError as exc:
        # Allow app to boot even if DB auth is misconfigured
        print("WARNING: Database connection failed during startup.")
        print(str(exc))


@app.get("/health")
def health_check() -> dict:
    return {
        "status": "ok",
        "database_url_set": bool(settings.DATABASE_URL),
        "openai_key_set": bool(settings.OPENAI_API_KEY),
    }


app.include_router(chat_router)
app.include_router(locomotive_router)

mount_chainlit(app=app, target="app/chainlit_app.py", path="/chat-ui")
