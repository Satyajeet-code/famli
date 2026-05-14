"""
Retirement API Routes

POST /api/retirement/chat    - one chat turn with Research Buddy.
GET  /api/retirement/history - fetch the user's full chat history.
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Header, Query

from app.controller.retirement_controller import RetirementController
from app.models.retirement_schemas import (
    ChatHistoryResponse,
    ChatRequest,
    ChatResponse,
)
from app.utils.logger import AppLogger

logger = AppLogger.get_logger(__file__)

router = APIRouter(prefix="/api/retirement", tags=["retirement"])


def _resolve_request_id(header_value: Optional[str]) -> str:
    return header_value or str(uuid.uuid4())


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
) -> ChatResponse:
    request_id = _resolve_request_id(x_request_id)
    logger.info(
        "request_id: '%s' POST /api/retirement/chat user_id=%d",
        request_id, payload.user_id,
    )
    return await RetirementController(request_id=request_id).chat(payload)


@router.get("/history", response_model=ChatHistoryResponse)
async def history(
    user_id: int = Query(..., gt=0),
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
) -> ChatHistoryResponse:
    request_id = _resolve_request_id(x_request_id)
    logger.info(
        "request_id: '%s' GET /api/retirement/history user_id=%d",
        request_id, user_id,
    )
    return await RetirementController(request_id=request_id).history(user_id)
