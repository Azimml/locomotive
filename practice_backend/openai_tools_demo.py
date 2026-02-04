import json
import os
from openai import OpenAI



MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

client = OpenAI()


def add_numbers(a: int, b: int) -> int:
    return a + b


tools = [
    {
        "type": "function",
        "name": "add_numbers",
        "description": "Add two integers and return the sum.",
        "parameters": {
            "type": "object",
            "properties": {
                "a": {"type": "integer"},
                "b": {"type": "integer"},
            },
            "required": ["a", "b"],
            "additionalProperties": False,
        },
        "strict": True,
    }
]

prompt = "What is 12 + 30? Use the add_numbers tool."

response = client.responses.create(
    model=MODEL,
    input=prompt,
    tools=tools,
)

# If the model calls a tool, run it locally and send the output back.
custom_tool_calls = [item for item in response.output if item.type == "custom_tool_call"]

if not custom_tool_calls:
    print(response.output_text)
    raise SystemExit(0)

outputs = []
for call in custom_tool_calls:
    args = json.loads(call.input)
    result = add_numbers(args["a"], args["b"])
    outputs.append(
        {
            "type": "custom_tool_call_output",
            "call_id": call.call_id,
            "output": json.dumps({"sum": result}),
        }
    )

final = client.responses.create(
    model=MODEL,
    previous_response_id=response.id,
    input=outputs,
)

print(final.output_text)