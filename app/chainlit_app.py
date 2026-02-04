import chainlit as cl

from app.services.ai import AiService


@cl.on_chat_start
async def on_chat_start():
    cl.user_session.set("history", [])
    await cl.Message(content="Hello! Ask me about locomotives.").send()


@cl.on_message
async def on_message(message: cl.Message):
    history = cl.user_session.get("history") or []
    history.append({"role": "user", "content": message.content})

    ai = AiService()
    result = ai.process_message(message.content, history)

    history.append({"role": "assistant", "content": result.get("content", "")})
    cl.user_session.set("history", history)

    await cl.Message(content=result.get("content", "")).send()
