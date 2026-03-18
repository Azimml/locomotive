"""Agent definition and run/stream helpers."""
from __future__ import annotations

import time
from typing import AsyncIterator

from agents import Agent, ModelSettings, Runner, set_tracing_disabled

from ..config import settings
from ..sources.prompts import SYSTEM_PROMPT
from .tools import ALL_TOOLS

# Disable tracing
set_tracing_disabled(True)

# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------

locomotive_agent = Agent(
    name="UTY AI Yordamchi",
    instructions=SYSTEM_PROMPT,
    model=settings.OPENAI_MODEL,
    model_settings=ModelSettings(temperature=0.3, max_tokens=2000),
    tools=ALL_TOOLS,
)


# ---------------------------------------------------------------------------
# Synchronous run (for REST API)
# ---------------------------------------------------------------------------

def run_sync(user_message: str, conversation_history: list[dict]) -> dict:
    """Run the agent synchronously. Returns {content, metadata}."""
    start = time.time()
    input_items = _build_input(user_message, conversation_history)

    result = Runner.run_sync(locomotive_agent, input=input_items, max_turns=5)

    processing_time = int((time.time() - start) * 1000)
    return {
        "content": result.final_output or "Javob olishda xatolik yuz berdi",
        "metadata": {"processingTime": processing_time},
    }


# ---------------------------------------------------------------------------
# Streaming run (for Chainlit)
# ---------------------------------------------------------------------------

async def run_streamed(
    user_message: str,
    conversation_history: list[dict],
) -> AsyncIterator[dict]:
    """Run the agent with streaming. Yields {type, content} events."""
    start = time.time()
    input_items = _build_input(user_message, conversation_history)

    result = Runner.run_streamed(locomotive_agent, input=input_items, max_turns=5)

    full_content = ""
    async for event in result.stream_events():
        if event.type == "raw_response_event":
            data = event.data
            if hasattr(data, "type") and data.type == "response.output_text.delta":
                token = data.delta
                full_content += token
                yield {"type": "token", "content": token}

    processing_time = int((time.time() - start) * 1000)
    yield {
        "type": "final",
        "content": full_content or result.final_output or "Javob olishda xatolik yuz berdi",
        "metadata": {"processingTime": processing_time},
    }


# ---------------------------------------------------------------------------
# Input builder
# ---------------------------------------------------------------------------

def _build_input(user_message: str, history: list[dict]) -> list[dict]:
    """Convert conversation history to input items for the agent."""
    items: list[dict] = []
    for msg in history[-10:]:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role in ("user", "assistant"):
            items.append({"role": role, "content": content})
    items.append({"role": "user", "content": user_message})
    return items
