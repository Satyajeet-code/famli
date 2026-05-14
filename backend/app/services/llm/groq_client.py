"""
Groq LLM Client

Thin async wrapper around the official `groq` Python SDK. Exposes a single
helper, chat_with_tools, that runs a chat completion where the model may
either reply with plain text (a string that the frontend renders to the
user, optionally containing a JSON block the frontend parses) or invoke
one of the supplied tools.

Configuration:
    GROQ_API_KEY  - required; raises at first call if missing.
    GROQ_MODEL    - optional; defaults to 'llama-3.3-70b-versatile'.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from groq import AsyncGroq

from app.utils.logger import AppLogger

logger = AppLogger.get_logger(__file__)


DEFAULT_MODEL = "llama-3.3-70b-versatile"


class GroqConfigurationError(RuntimeError):
    """Raised when required Groq configuration is missing."""


@dataclass(frozen=True)
class ChatTurnResult:
    """One assistant turn: free-text content and/or tool calls."""
    content: str
    tool_calls: List[Dict[str, Any]]


class GroqClient:
    """Async Groq client backed by the official SDK."""

    def __init__(
        self,
        request_id: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self.request_id = request_id
        self.model = model or os.getenv("GROQ_MODEL", DEFAULT_MODEL)
        logger.info(
            "request_id: '%s' GroqClient initialized with model='%s'",
            self.request_id, self.model,
        )

    def _build_sdk_client(self) -> AsyncGroq:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            logger.error(
                "request_id: '%s' GROQ_API_KEY environment variable is not set",
                self.request_id,
            )
            raise GroqConfigurationError("GROQ_API_KEY is not configured")
        return AsyncGroq(api_key=api_key)

    async def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        temperature: float = 0.2,
    ) -> ChatTurnResult:
        """
        Multi-turn chat completion. The model may respond with plain text
        or by invoking one of the supplied tools.

        Args:
            messages: OpenAI-style message list (system + history + new turn).
            tools: Tool definitions in OpenAI / Groq format.
            temperature: Sampling temperature for the free-text reply.

        Returns:
            ChatTurnResult with content (string) and any tool_calls.
        """
        client = self._build_sdk_client()

        logger.info(
            "request_id: '%s' Calling Groq chat_with_tools model='%s' msg_count=%d",
            self.request_id, self.model, len(messages),
        )

        completion = await client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            messages=messages,
            tools=tools,
        )

        # TODO REMOVE: temporary debug dump of full completion to logs/llm_responses.txt
        try:
            from datetime import datetime
            from pathlib import Path
            Path("logs").mkdir(exist_ok=True)
            with open("logs/llm_responses.txt", "a", encoding="utf-8") as fp:
                fp.write(
                    f"--- ----------------------------------- "
                    f"request_id={self.request_id} ---\n"
                )
                fp.write(completion.model_dump_json(indent=2))
                fp.write("\n\n")
        except Exception as dump_exc:
            logger.warning("Failed to dump completion: %s", dump_exc)
        # TODO REMOVE: temporary debug dump of full completion to logs/llm_responses.txt

        message = completion.choices[0].message
        content = message.content or ""

        tool_calls: List[Dict[str, Any]] = []
        for call in (message.tool_calls or []):
            func = call.function
            args_raw = func.arguments or "{}"
            try:
                args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
            except json.JSONDecodeError as exc:
                logger.error(
                    "request_id: '%s' Tool args were not valid JSON: %s",
                    self.request_id, args_raw, exc_info=True,
                )
                raise ValueError("Tool arguments were not valid JSON") from exc
            tool_calls.append({"id": call.id, "name": func.name, "arguments": args})

        logger.info(
            "request_id: '%s' Groq chat_with_tools returned content_len=%d tool_calls=%d",
            self.request_id, len(content), len(tool_calls),
        )
        return ChatTurnResult(content=content, tool_calls=tool_calls)
