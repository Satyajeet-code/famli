"""
Auth Controller

Thin orchestration between the auth routes and AuthService.
"""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status

from app.models.retirement_schemas import (
    LoginRequest,
    SignupRequest,
    TokenResponse,
)
from app.services.auth.auth_service import AuthService
from app.utils.logger import AppLogger

logger = AppLogger.get_logger(__file__)


class AuthController:
    def __init__(self, request_id: Optional[str] = None) -> None:
        self.request_id = request_id
        self._service = AuthService(request_id=request_id)
        logger.info("request_id: '%s' AuthController initialized", self.request_id)

    async def signup(self, payload: SignupRequest) -> TokenResponse:
        try:
            return await self._service.signup(payload)
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(
                "request_id: '%s' Unexpected error during signup: %s",
                self.request_id, exc, exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Signup failed",
            )

    async def login(self, payload: LoginRequest) -> TokenResponse:
        try:
            return await self._service.login(payload)
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(
                "request_id: '%s' Unexpected error during login: %s",
                self.request_id, exc, exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Login failed",
            )
