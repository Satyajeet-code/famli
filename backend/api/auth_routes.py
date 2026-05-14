"""
Auth API Routes

POST /api/auth/signup - create a new account, returns a JWT.
POST /api/auth/login  - exchange credentials for a JWT.
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Header

from app.controller.auth_controller import AuthController
from app.models.retirement_schemas import (
    LoginRequest,
    SignupRequest,
    TokenResponse,
)
from app.utils.logger import AppLogger

logger = AppLogger.get_logger(__file__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _resolve_request_id(header_value: Optional[str]) -> str:
    return header_value or str(uuid.uuid4())


@router.post("/signup", response_model=TokenResponse, status_code=201)
async def signup(
    payload: SignupRequest,
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
) -> TokenResponse:
    request_id = _resolve_request_id(x_request_id)
    logger.info("request_id: '%s' POST /api/auth/signup", request_id)
    return await AuthController(request_id=request_id).signup(payload)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
) -> TokenResponse:
    request_id = _resolve_request_id(x_request_id)
    logger.info("request_id: '%s' POST /api/auth/login", request_id)
    return await AuthController(request_id=request_id).login(payload)
