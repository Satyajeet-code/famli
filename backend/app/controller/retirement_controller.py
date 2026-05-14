"""
Retirement Controller

Orchestrates the chat endpoint between the API layer and RetirementService.
"""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status

from app.models.retirement_schemas import (
    ChatHistoryItem,
    ChatHistoryResponse,
    ChatRequest,
    ChatResponse,
)
from app.services.retirement.retirement_service import RetirementService
from app.utils.logger import AppLogger

logger = AppLogger.get_logger(__file__)


class RetirementController:
    """Per-request controller for the retirement chat endpoint."""

    def __init__(self, request_id: Optional[str] = None) -> None:
        self.request_id = request_id
        self._service = RetirementService(request_id=request_id)
        logger.info("request_id: '%s' RetirementController initialized", self.request_id)

    async def chat(self, payload: ChatRequest) -> ChatResponse:
        try:
            return await self._service.chat_turn(
                user_id=payload.user_id,
                message=payload.message,
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(
                "request_id: '%s' Unexpected error in chat turn: %s",
                self.request_id, exc, exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Chat turn failed",
            )

    async def history(self, user_id: int) -> ChatHistoryResponse:
        try:
            rows = await self._service.get_history(user_id)
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(
                "request_id: '%s' Unexpected error fetching history: %s",
                self.request_id, exc, exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch chat history",
            )
        return ChatHistoryResponse(messages=[ChatHistoryItem(**r) for r in rows])
