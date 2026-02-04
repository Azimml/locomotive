import json
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from openai import OpenAI

from db.store import list_items

router = APIRouter()

MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


class AIRequest(BaseModel):
    prompt: str = Field(min_length=1)


class AIResponse(BaseModel):
    answer: str
    used_tools: bool


def get_items_stats() -> dict:
    items = list_items()
    return {
        "items_count": len(items),
        "last_id": items[-1].id if items else None,
    }


@router.post("/ask", response_model=AIResponse)
def ai_ask(payload: AIRequest):
    tools = [
        {
            "type": "function",
            "name": "get_items_stats",
            "description": "Get item stats from the in-memory store.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            "strict": True,
        }
    ]

    try:
        client = OpenAI()
        response = client.responses.create(
            model=MODEL,
            input=payload.prompt,
            tools=tools,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    tool_calls = [item for item in response.output if item.type == "custom_tool_call"]
    if not tool_calls:
        return AIResponse(answer=response.output_text, used_tools=False)

    outputs = []
    for call in tool_calls:
        if call.name == "get_items_stats":
            output = get_items_stats()
        else:
            output = {"error": f"Unknown tool: {call.name}"}

        outputs.append(
            {
                "type": "custom_tool_call_output",
                "call_id": call.call_id,
                "output": json.dumps(output),
            }
        )

    try:
        final = client.responses.create(
            model=MODEL,
            previous_response_id=response.id,
            input=outputs,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return AIResponse(answer=final.output_text, used_tools=True)
