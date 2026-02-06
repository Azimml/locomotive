from __future__ import annotations

import json
import re
import time
from typing import Any

from openai import OpenAI

from ..config import settings
from .tool_executor import ToolExecutorService
from .tools import locomotive_tools
from .prompts import SYSTEM_PROMPT


class AiService:
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL or "gpt-4o-mini"
        self.tool_executor = ToolExecutorService()
        self.tool_labels: dict[str, str] = {
            "get_total_locomotives_count": "Lokomotivlar sonini olish",
            "get_locomotives_by_state": "Holat bo'yicha ma'lumotlar",
            "get_stats": "Statistika yuklanmoqda",
            "get_locomotive_types": "Lokomotiv turlari tekshirilmoqda",
            "get_locomotive_models": "Model ma'lumotlari olinmoqda",
            "get_active_repairs": "Faol ta'mirlar tekshirilmoqda",
            "get_locomotive_last_repair": "Ta'mir tarixini olish",
            "get_all_last_repairs": "Barcha ta'mirlar yuklanmoqda",
            "search_locomotive_by_name": "Lokomotiv qidirilmoqda",
            "get_locomotive_detailed_info": "Batafsil ma'lumot olinmoqda",
            "get_current_inspections": "Joriy tekshiruvlar",
            "get_total_inspection_counts": "Tekshiruv statistikasi",
            "get_depo_info": "Depo ma'lumotlari olinmoqda",
            "get_all_depos_info": "Barcha depolar tekshirilmoqda",
            "get_repair_stats_by_year": "Yillik statistika yuklanmoqda",
        }

    def analyze_intent(self, user_message: str) -> dict:
        message = user_message.lower()
        expected_tools: list[str] = []
        steps: list[dict] = []

        steps.append({"id": "analyze", "text": "So'rovni tahlil qilish"})

        locomotive_match = re.search(r"\b\d{3,4}\b", user_message)
        is_location_query = any(
            phrase in message
            for phrase in ["qayerda", "joylashuv", "hozir qayerda", "qaysi joy", "hozir"]
        )

        if is_location_query and locomotive_match:
            expected_tools.append("search_locomotive_by_name")
            steps.append(
                {
                    "id": "location_search",
                    "text": f"{locomotive_match.group(0)} lokomotivning joylashuvini aniqlayman",
                    "toolName": "search_locomotive_by_name",
                }
            )
        elif is_location_query and not locomotive_match:
            expected_tools.append("search_locomotive_by_name")
            steps.append(
                {
                    "id": "context_search",
                    "text": "Oldingi suhbatdagi lokomotiv joylashuvini aniqlayman",
                    "toolName": "search_locomotive_by_name",
                }
            )

        if any(k in message for k in ["nechta", "soni", "jami"]):
            if "lokomotiv" in message:
                expected_tools.append("get_total_locomotives_count")
            if "tekshiruv" in message or "inspeksiya" in message:
                expected_tools.append("get_total_inspection_counts")

        if any(k in message for k in ["holat", "ishlamoqda", "ta'mirda"]):
            expected_tools.append("get_locomotives_by_state")

        if "statistika" in message or "hisobot" in message:
            expected_tools.append("get_stats")
            if "yil" in message:
                expected_tools.append("get_repair_stats_by_year")

        if "tur" in message and "lokomotiv" in message:
            expected_tools.append("get_locomotive_types")

        if "model" in message:
            expected_tools.append("get_locomotive_models")

        if "ta'mir" in message and ("faol" in message or "hozirgi" in message):
            expected_tools.append("get_active_repairs")

        if "ta'mir" in message and "oxirgi" in message:
            if "barcha" in message or "hamma" in message:
                expected_tools.append("get_all_last_repairs")
            else:
                expected_tools.append("get_locomotive_last_repair")

        if any(k in message for k in ["qidir", "top", "izla"]):
            expected_tools.append("search_locomotive_by_name")

        if "batafsil" in message or "ma'lumot" in message:
            expected_tools.append("get_locomotive_detailed_info")

        if "tekshiruv" in message and "hozir" in message:
            expected_tools.append("get_current_inspections")

        if "depo" in message:
            if "barcha" in message or "hamma" in message:
                expected_tools.append("get_all_depos_info")
            else:
                expected_tools.append("get_depo_info")

        for idx, tool_name in enumerate(expected_tools):
            steps.append(
                {
                    "id": f"tool_{idx}",
                    "text": self.tool_labels.get(tool_name, f"{tool_name} bajarilmoqda"),
                    "toolName": tool_name,
                }
            )

        if not expected_tools:
            steps.append({"id": "fetch", "text": "Ma'lumotlar yuklanmoqda"})

        steps.append({"id": "generate", "text": "Javob tayyorlanmoqda"})

        return {
            "intent": self.detect_intent_category(message),
            "expectedTools": expected_tools,
            "steps": steps,
        }

    def detect_intent_category(self, message: str) -> str:
        if "qidir" in message or "top" in message:
            return "search"
        if "statistika" in message or "hisobot" in message:
            return "statistics"
        if "ta'mir" in message:
            return "repair"
        if "tekshiruv" in message:
            return "inspection"
        if "depo" in message:
            return "depot"
        if "nechta" in message or "soni" in message:
            return "count"
        return "general"

    def process_message(
        self, user_message: str, conversation_history: list[dict]
    ) -> dict:
        start_time = time.time()
        tools_used: list[str] = []

        intent_analysis = self.analyze_intent(user_message)

        enhanced_message = self.enhance_message_with_context(
            user_message, conversation_history
        )
        final_message = enhanced_message or user_message

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *self.format_conversation_history(conversation_history),
            {"role": "user", "content": final_message},
        ]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=locomotive_tools,
            tool_choice="auto",
            temperature=0.3,
            max_tokens=2000,
        )

        assistant_message = response.choices[0].message
        iteration_count = 0
        max_iterations = 5

        while (
            assistant_message.tool_calls
            and len(assistant_message.tool_calls) > 0
            and iteration_count < max_iterations
        ):
            iteration_count += 1
            messages.append(assistant_message)

            tool_responses: list[dict[str, Any]] = []

            for tool_call in assistant_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments or "{}")

                tools_used.append(function_name)
                result = self.tool_executor.execute_function(function_name, function_args)

                tool_responses.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(
                            {
                                "success": result.get("success"),
                                "data": result.get("data"),
                                "summary": result.get("summary"),
                            },
                            ensure_ascii=False,
                        ),
                    }
                )

            messages.extend(tool_responses)

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=locomotive_tools,
                tool_choice="auto",
                temperature=0.3,
                max_tokens=2000,
            )
            assistant_message = response.choices[0].message

        processing_time = int((time.time() - start_time) * 1000)
        return {
            "content": assistant_message.content or "Javob olishda xatolik yuz berdi",
            "metadata": {
                "toolsUsed": tools_used or None,
                "processingTime": processing_time,
                "intentAnalysis": intent_analysis,
            },
        }

    def stream_message(
        self, user_message: str, conversation_history: list[dict]
    ):
        start_time = time.time()
        tools_used: list[str] = []

        intent_analysis = self.analyze_intent(user_message)

        enhanced_message = self.enhance_message_with_context(
            user_message, conversation_history
        )
        final_message = enhanced_message or user_message

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *self.format_conversation_history(conversation_history),
            {"role": "user", "content": final_message},
        ]

        max_iterations = 5
        iteration_count = 0
        full_content = ""

        while iteration_count < max_iterations:
            iteration_count += 1
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=locomotive_tools,
                tool_choice="auto",
                temperature=0.3,
                max_tokens=2000,
                stream=True,
            )

            tool_calls: dict[int, dict[str, Any]] = {}
            finish_reason = None

            for chunk in response:
                choice = chunk.choices[0]
                if choice.finish_reason:
                    finish_reason = choice.finish_reason

                delta = choice.delta
                if delta is None:
                    continue

                if delta.content:
                    full_content += delta.content
                    yield {"type": "token", "content": delta.content}

                if delta.tool_calls:
                    for tool_call in delta.tool_calls:
                        idx = tool_call.index or 0
                        entry = tool_calls.setdefault(
                            idx,
                            {
                                "id": tool_call.id,
                                "function": {"name": "", "arguments": ""},
                            },
                        )
                        if tool_call.id:
                            entry["id"] = tool_call.id
                        if tool_call.function:
                            if tool_call.function.name:
                                entry["function"]["name"] = tool_call.function.name
                            if tool_call.function.arguments:
                                entry["function"]["arguments"] += tool_call.function.arguments

            if finish_reason != "tool_calls":
                break

            if not tool_calls:
                break

            tool_calls_list: list[dict[str, Any]] = []
            for idx in sorted(tool_calls.keys()):
                call = tool_calls[idx]
                tool_calls_list.append(
                    {
                        "id": call.get("id") or f"call_{idx}",
                        "type": "function",
                        "function": {
                            "name": call["function"]["name"],
                            "arguments": call["function"]["arguments"],
                        },
                    }
                )

            messages.append({"role": "assistant", "tool_calls": tool_calls_list})

            for tool_call in tool_calls_list:
                function_name = tool_call["function"]["name"]
                function_args = json.loads(tool_call["function"]["arguments"] or "{}")
                tools_used.append(function_name)
                result = self.tool_executor.execute_function(function_name, function_args)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps(
                            {
                                "success": result.get("success"),
                                "data": result.get("data"),
                                "summary": result.get("summary"),
                            },
                            ensure_ascii=False,
                        ),
                    }
                )

        processing_time = int((time.time() - start_time) * 1000)
        yield {
            "type": "final",
            "content": full_content or "Javob olishda xatolik yuz berdi",
            "metadata": {
                "toolsUsed": tools_used or None,
                "processingTime": processing_time,
                "intentAnalysis": intent_analysis,
            },
        }

    def enhance_message_with_context(
        self, user_message: str, conversation_history: list[dict]
    ) -> str | None:
        message = user_message.lower().strip()

        is_location_query = any(
            phrase in message
            for phrase in ["qayerda", "joylashuv", "hozir", "qaysi joy"]
        )
        if not is_location_query:
            return None

        recent_messages = conversation_history[-6:]
        for msg in reversed(recent_messages):
            locomotive_matches = re.findall(
                r"(?:UZ-EL\s*)?(\d{3,4})|lokomotiv[:\s]*(\d{3,4})",
                msg.get("content", ""),
                flags=re.IGNORECASE,
            )
            if locomotive_matches:
                number = next((m[0] or m[1] for m in locomotive_matches if (m[0] or m[1])), None)
                if number:
                    return f"{number} lokomotiv {user_message}"
        return None

    def format_conversation_history(self, history: list[dict]) -> list[dict]:
        recent_history = history[-10:]
        return [
            {"role": msg["role"], "content": msg["content"]} for msg in recent_history
        ]
