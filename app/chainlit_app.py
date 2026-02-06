import os
import time
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from app.config import settings

os.environ.setdefault("CHAINLIT_AUTH_SECRET", settings.CHAINLIT_AUTH_SECRET)
if settings.CHAINLIT_PERSISTENCE_ENABLED:
    parsed = urlparse(settings.DATABASE_URL)
    query = dict(parse_qsl(parsed.query))
    query.setdefault("options", f"-csearch_path={settings.CHAINLIT_DB_SCHEMA}")
    chainlit_db_url = urlunparse(parsed._replace(query=urlencode(query)))
    os.environ["DATABASE_URL"] = chainlit_db_url

import chainlit as cl

from app.services.ai import AiService


@cl.password_auth_callback
def password_auth_callback(username: str, password: str):
    if (
        username == settings.CHAINLIT_AUTH_USERNAME
        and password == settings.CHAINLIT_AUTH_PASSWORD
    ):
        return cl.User(identifier=username, display_name=settings.CHAINLIT_AUTH_FULL_NAME)
    return None


@cl.on_chat_start
async def on_chat_start():
    cl.user_session.set("history", [])
    await cl.Message(content="Hello! Ask me about locomotives.").send()


@cl.on_chat_resume
async def on_chat_resume(thread):    
    cl.user_session.set("history", [])


@cl.on_message
async def on_message(message: cl.Message):
    start_total = time.perf_counter()
    history = cl.user_session.get("history") or []
    history.append({"role": "user", "content": message.content})

    ai = AiService()
    start_ai = time.perf_counter()
    stream = ai.stream_message(message.content, history)

    assistant_msg = cl.Message(content="")
    await assistant_msg.send()

    full_content = ""
    metadata = {}
    for event in stream:
        if event.get("type") == "token":
            chunk = event.get("content") or ""
            full_content += chunk
            await assistant_msg.stream_token(chunk)
        elif event.get("type") == "final":
            metadata = event.get("metadata") or {}
            if event.get("content"):
                full_content = event.get("content") or full_content

    history.append({"role": "assistant", "content": full_content})
    cl.user_session.set("history", history)
    await assistant_msg.update()

    ai_ms = (time.perf_counter() - start_ai) * 1000
    total_ms = (time.perf_counter() - start_total) * 1000
    print(
        f"[chainlit] on_message ai_ms={ai_ms:.1f} total_ms={total_ms:.1f} "
        f"persistence={'on' if settings.CHAINLIT_PERSISTENCE_ENABLED else 'off'}"
    )
