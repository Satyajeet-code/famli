"""
Retirement Chat Service

LLM-driven chatbot that collects the 7 retirement inputs from the user
and computes the corpus through a Groq tool call.

Per-turn flow:
    1. Persist the user's message to chat_history.
    2. Load the last MAX_HISTORY_TURNS turns for this user.
    3. Call Groq with system prompt + history + the calculate tool.
    4a. Free-text reply -> persist and return.
    4b. Tool call -> run calculate_retirement_corpus, append tool result
        as a `tool` role message, call Groq once more for the natural
        language summary, persist and return.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import insert, select

from app.models.retirement_schemas import ChatResponse, CorpusResult
from app.services.database.db_engine import AsyncSessionLocal, metadata
from app.services.llm.groq_client import GroqClient
from app.services.retirement.prompts import get_system_prompt
from app.services.retirement.tools import (
    CALCULATE_TOOL,
    TOOL_NAME,
    calculate_retirement_corpus,
)
from app.utils.logger import AppLogger

logger = AppLogger.get_logger(__file__)


MAX_HISTORY_TURNS = 10


class RetirementService:
    """Chat-driven retirement input collection and corpus calculation."""

    def __init__(
        self,
        request_id: Optional[str] = None,
        llm_client: Optional[GroqClient] = None,
    ) -> None:
        self.request_id = request_id
        self._llm_client = llm_client
        logger.info("request_id: '%s' RetirementService initialized", self.request_id)

    async def chat_turn(self, user_id: int, message: str) -> ChatResponse:
        """Handle one chat turn from the user."""
        await self._ensure_user_exists(user_id)

        message_stripped = (message or "").strip()
        if not message_stripped:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="message must not be empty",
            )

        # Persist user turn first so it survives an LLM failure.
        await self._append_history(user_id, "user", message_stripped)

        history = await self._load_history(user_id)
        established = await self._load_established_inputs(user_id)

        messages: List[Dict[str, Any]] = [{"role": "system", "content": get_system_prompt()}]
        if established:
            messages.append({
                "role": "system",
                "content": (
                    "PREVIOUSLY ESTABLISHED VALUES (from this user's last completed calculation). "
                    "Treat these as authoritative defaults — the user already gave them in an earlier "
                    "session. Do NOT ask for them again unless the user volunteers a change.\n"
                    f"{json.dumps(established, default=str)}"
                ),
            })
        messages.extend({"role": h["role"], "content": h["content"]} for h in history)

        client = self._llm_client or GroqClient(request_id=self.request_id)

        # TODO REMOVE: temporary debug dump of LLM input messages
        try:
            from pathlib import Path
            Path("logs").mkdir(exist_ok=True)
            with open("logs/llm_inputs.txt", "a", encoding="utf-8") as fp:
                fp.write(f"--- request_id={self.request_id} call=initial ---\n")
                fp.write(json.dumps(messages, indent=2, default=str))
                fp.write("\n\n")
        except Exception as dump_exc:
            logger.warning("Failed to dump LLM input: %s", dump_exc)
        # TODO REMOVE: temporary debug dump of LLM input messages

        response = await client.chat_with_tools(messages=messages, tools=[CALCULATE_TOOL])

        if not response.tool_calls:
            assistant_text = response.content or (
                "Sorry, I lost my train of thought. Could you repeat that?"
            )
            await self._append_history(user_id, "assistant", assistant_text)
            return ChatResponse(bot_message=assistant_text, corpus=None)

        # Tool-call branch.
        messages.append({
            "role": "assistant",
            "content": response.content or None,
            "tool_calls": [
                {
                    "id": call["id"],
                    "type": "function",
                    "function": {
                        "name": call["name"],
                        "arguments": json.dumps(call.get("arguments") or {}),
                    },
                }
                for call in response.tool_calls
            ],
        })

        corpus_result: Optional[CorpusResult] = None
        for call in response.tool_calls:
            if call["name"] != TOOL_NAME:
                llm_content = json.dumps({"error": f"Unknown tool: {call['name']}"})
            else:
                args = call.get("arguments") or {}
                llm_content, corpus = await calculate_retirement_corpus(
                    user_id=user_id, **args
                )
                corpus_result = corpus or corpus_result

            messages.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "name": call["name"],
                "content": llm_content,
            })

            # TODO REMOVE: temporary debug dump of tool result fed back to the LLM
            try:
                from pathlib import Path
                Path("logs").mkdir(exist_ok=True)
                with open("logs/tool_results.txt", "a", encoding="utf-8") as fp:
                    fp.write(
                        f"--- request_id={self.request_id} "
                        f"tool={call['name']} tool_call_id={call['id']} ---\n"
                    )
                    fp.write(llm_content)
                    fp.write("\n\n")
            except Exception as dump_exc:
                logger.warning("Failed to dump tool result: %s", dump_exc)
            # TODO REMOVE: temporary debug dump of tool result fed back to the LLM

        # TODO REMOVE: temporary debug dump of LLM input messages (followup call)
        try:
            from pathlib import Path
            Path("logs").mkdir(exist_ok=True)
            with open("logs/llm_inputs.txt", "a", encoding="utf-8") as fp:
                fp.write(f"--- request_id={self.request_id} call=followup ---\n")
                fp.write(json.dumps(messages, indent=2, default=str))
                fp.write("\n\n")
        except Exception as dump_exc:
            logger.warning("Failed to dump LLM input: %s", dump_exc)
        # TODO REMOVE: temporary debug dump of LLM input messages (followup call)

        followup = await client.chat_with_tools(messages=messages, tools=[CALCULATE_TOOL])
        assistant_text = followup.content or (
            "I've computed your retirement corpus. Let me know if you'd like to adjust anything."
        )
        await self._append_history(user_id, "assistant", assistant_text)
        return ChatResponse(bot_message=assistant_text, corpus=corpus_result)

    async def get_history(self, user_id: int) -> List[Dict[str, Any]]:
        """Return the user's full chat history ordered chronologically."""
        await self._ensure_user_exists(user_id)

        chat = metadata.tables["chat_history_dummy"]
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(chat.c.id, chat.c.role, chat.c.message, chat.c.created_at)
                .where(chat.c.user_id == user_id)
                .order_by(chat.c.created_at.asc())
            )
            rows = list(result.all())
        return [
            {
                "id": r.id,
                "role": r.role,
                "message": r.message,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    # ------------------------------------------------------------------ #
    # DB                                                                 #
    # ------------------------------------------------------------------ #

    async def _ensure_user_exists(self, user_id: int) -> None:
        users = metadata.tables["users_dummy"]
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(users.c.id).where(users.c.id == user_id)
            )
            if result.scalar() is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found",
                )

    async def _load_established_inputs(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Return the user's last persisted retirement inputs (or None if they've
        never completed a calculation). Used to inject authoritative defaults
        into the LLM context so values survive past the chat history window.
        """
        table = metadata.tables["retirement_inputs_dummy"]
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(table).where(table.c.user_id == user_id)
            )
            row = result.mappings().first()
        if row is None:
            return None
        return {
            k: v for k, v in dict(row).items()
            if k not in ("user_id", "updated_at") and v is not None
        }

    async def _load_history(self, user_id: int) -> List[Dict[str, str]]:
        chat = metadata.tables["chat_history_dummy"]
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(chat.c.role, chat.c.message, chat.c.created_at)
                .where(chat.c.user_id == user_id)
                .order_by(chat.c.created_at.desc())
                .limit(MAX_HISTORY_TURNS)
            )
            rows = list(result.all())
        rows.reverse()
        return [{"role": r.role, "content": r.message} for r in rows]

    async def _append_history(self, user_id: int, role: str, message: str) -> None:
        chat = metadata.tables["chat_history_dummy"]
        async with AsyncSessionLocal() as session:
            await session.execute(
                insert(chat).values(user_id=user_id, role=role, message=message)
            )
            await session.commit()
