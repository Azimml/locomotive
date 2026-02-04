import json
import os
import logging

import pandas as pd
from fastapi import FastAPI, HTTPException
from openai import OpenAI
from pydantic import BaseModel, Field
from sqlalchemy import create_engine

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:12345@localhost:5432/dejurka",
)

app = FastAPI(title="Stats API")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stats-ai")


def _get_engine():
    return create_engine(DATABASE_URL, pool_pre_ping=True)


def _load_table(table_name: str, columns: list[str] | None = None):
    engine = _get_engine()
    return pd.read_sql_table(table_name, con=engine, columns=columns)


def _records_without_nan(df: pd.DataFrame):
    cleaned = df.astype(object).where(pd.notna(df), None)
    return cleaned.to_dict(orient="records")


class StateCount(BaseModel):
    state: str | None
    count: int


class Stats(BaseModel):
    total_locomotives: int
    total_models: int
    state_counts: list[StateCount]


class AIRequest(BaseModel):
    prompt: str = Field(min_length=1)


class AIResponse(BaseModel):
    answer: str
    used_tools: bool


def _get_stats_payload() -> dict:
    stats = get_stats()
    return stats.dict()


def _count_by_state(state_query: str) -> dict:
    stats = get_stats()
    normalized = (state_query or "").strip().lower()
    if not normalized:
        return {
            "error": "Missing state",
            "available_states": [sc.state for sc in stats.state_counts],
        }

    # Try direct match (case-insensitive)
    for sc in stats.state_counts:
        if (sc.state or "").strip().lower() == normalized:
            return {"state": sc.state, "count": sc.count}

    # Try common synonyms for reserve
    reserve_aliases = {"reserve", "rezerv", "in_reserve", "in-reserve"}
    if normalized in reserve_aliases:
        for sc in stats.state_counts:
            if (sc.state or "").strip().lower() in reserve_aliases:
                return {"state": sc.state, "count": sc.count}

    return {
        "error": f"State not found: {state_query}",
        "available_states": [sc.state for sc in stats.state_counts],
    }


@app.get("/stats", response_model=Stats)
def get_stats():
    df_loco = _load_table("locomotive_locomotive", columns=["id", "state"])
    df_models = _load_table("locomotive_locomotivemodel", columns=["id"])
    state_counts = (
        df_loco["state"]
        .value_counts(dropna=False)
        .rename_axis("state")
        .reset_index(name="count")
        .sort_values(by="state")
    )
    return Stats(
        total_locomotives=int(len(df_loco.index)),
        total_models=int(len(df_models.index)),
        state_counts=[StateCount(**row) for row in _records_without_nan(state_counts)],
    )


@app.post("/ai/ask", response_model=AIResponse)
def ai_ask(payload: AIRequest):
    tools = [
        {
            "type": "function",
            "name": "get_stats",
            "description": "Fetch locomotive stats (totals and state counts).",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            "strict": True,
        }
        ,
        {
            "type": "function",
            "name": "get_count_by_state",
            "description": "Get locomotive count for a specific state (e.g., reserve).",
            "parameters": {
                "type": "object",
                "properties": {
                    "state": {"type": "string"},
                },
                "required": ["state"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    ]

    prompt_lower = payload.prompt.lower()
    if "reserve" in prompt_lower or "rezerv" in prompt_lower:
        tool_choice = {"type": "function", "name": "get_count_by_state"}
    else:
        tool_choice = "required"

    try:
        logger.info("AI prompt: %s", payload.prompt)
        logger.info("Tool choice: %s", tool_choice)
        client = OpenAI()
        response = client.responses.create(
            model=MODEL,
            input=payload.prompt,
            tools=tools,
            tool_choice=tool_choice,
            parallel_tool_calls=False,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    tool_calls = [
        item
        for item in response.output
        if getattr(item, "type", None)
        in ("custom_tool_call", "tool_call", "function_call")
    ]
    logger.info("Tool calls found: %d", len(tool_calls))
    if not tool_calls:
        logger.info("No tool calls. output_text=%s", response.output_text)
        if "reserve" in prompt_lower or "rezerv" in prompt_lower:
            fallback = _count_by_state("reserve")
            return AIResponse(
                answer=f"Reserve count: {fallback.get('count')}",
                used_tools=False,
            )
        return AIResponse(answer=response.output_text, used_tools=False)

    outputs = []
    for call in tool_calls:
        call_name = getattr(call, "name", None)
        if call_name is None and getattr(call, "function", None):
            call_name = getattr(call.function, "name", None)

        logger.info("Tool call name: %s", call_name)
        if call_name == "get_stats":
            output = _get_stats_payload()
        elif call_name == "get_count_by_state":
            args = {}
            if getattr(call, "input", None):
                args = json.loads(call.input)
            elif getattr(call, "arguments", None):
                args = json.loads(call.arguments)
            elif getattr(call, "function", None) and getattr(
                call.function, "arguments", None
            ):
                args = json.loads(call.function.arguments)
            logger.info("Tool args: %s", args)
            output = _count_by_state(args.get("state", ""))
        else:
            output = {"error": f"Unknown tool: {call_name}"}

        call_id = getattr(call, "call_id", None) or getattr(call, "id", None)
        logger.info("Tool output: %s", output)
        outputs.append(
            {
                "type": "custom_tool_call_output",
                "call_id": call_id,
                "output": json.dumps(output),
            }
        )

    try:
        final = client.responses.create(
            model=MODEL,
            previous_response_id=response.id,
            input=outputs,
            tools=tools,
            tool_choice="auto",
            parallel_tool_calls=False,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    logger.info("Final answer: %s", final.output_text)
    return AIResponse(answer=final.output_text, used_tools=True)
