import os
import re
import time
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests

from app.config import settings

os.environ.setdefault("CHAINLIT_AUTH_SECRET", settings.CHAINLIT_AUTH_SECRET)
if settings.CHAINLIT_PERSISTENCE_ENABLED:
    parsed = urlparse(settings.DATABASE_URL)
    query = dict(parse_qsl(parsed.query))
    query.setdefault("options", f"-csearch_path={settings.CHAINLIT_DB_SCHEMA}")
    chainlit_db_url = urlunparse(parsed._replace(query=urlencode(query)))
    os.environ["DATABASE_URL"] = chainlit_db_url

import chainlit as cl

from app.agent import core as agent


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
    await cl.Message(content="Assalomu alekum! Locomotive AI Chat botiga xush kelibsiz!").send()


@cl.on_chat_resume
async def on_chat_resume(thread):
    cl.user_session.set("history", [])


@cl.on_message
async def on_message(message: cl.Message):
    start_total = time.perf_counter()
    history = cl.user_session.get("history") or []
    history.append({"role": "user", "content": message.content})

    assistant_msg = cl.Message(content="")
    await assistant_msg.send()

    full_content = ""
    async for event in agent.run_streamed(message.content, history):
        if event.get("type") == "token":
            chunk = event.get("content") or ""
            full_content += chunk
            await assistant_msg.stream_token(chunk)
        elif event.get("type") == "final":
            if event.get("content"):
                full_content = event.get("content") or full_content

    # Extract and display photo if present
    photo_match = re.search(r"\[PHOTO_URL:(https?://[^\]]+)\]", full_content)
    if photo_match:
        photo_url = photo_match.group(1)
        # Remove the marker from displayed content
        clean_content = full_content.replace(photo_match.group(0), "").strip()
        assistant_msg.content = clean_content
        await assistant_msg.update()

        # Download and send photo as separate message
        try:
            resp = requests.get(photo_url, timeout=10, verify=False)
            if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image"):
                ext = photo_url.rsplit(".", 1)[-1] if "." in photo_url else "jpg"
                photo_el = cl.Image(content=resp.content, name=f"photo.{ext}", display="inline")
                await cl.Message(content="", elements=[photo_el]).send()
        except Exception:
            pass  # silently skip if photo download fails

        full_content = clean_content

    history.append({"role": "assistant", "content": full_content})
    cl.user_session.set("history", history)
    await assistant_msg.update()

    total_ms = (time.perf_counter() - start_total) * 1000
    print(f"[chainlit] on_message total_ms={total_ms:.1f}")
