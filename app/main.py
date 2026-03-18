from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings

app = FastAPI(title="Locomotive AI", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.CORS_ORIGINS),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict:
    return {
        "status": "ok",
        "openai_key_set": bool(settings.OPENAI_API_KEY),
    }


from chainlit.utils import mount_chainlit

mount_chainlit(app=app, target="app/chainlit_app.py", path="/chat-ui")
