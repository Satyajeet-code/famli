"""
Auth Service

Signup and login operations against the reflected `users` table. Passwords
are hashed with bcrypt; successful login issues a short-lived JWT.
"""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import insert, select

from app.models.retirement_schemas import (
    LoginRequest,
    SignupRequest,
    TokenResponse,
)
from app.services.database.db_engine import AsyncSessionLocal, metadata
from app.services.retirement.prompts import get_welcome_message
from app.utils.auth import create_access_token, hash_password, verify_password
from app.utils.logger import AppLogger

logger = AppLogger.get_logger(__file__)


class AuthService:
    """User signup and login backed by the reflected users table."""

    def __init__(self, request_id: Optional[str] = None) -> None:
        self.request_id = request_id
        logger.info("request_id: '%s' AuthService initialized", self.request_id)

    async def signup(self, payload: SignupRequest) -> TokenResponse:
        """
        Create a user and return an access token.

        The user row and the bot's opening turn in chat_history are
        written in the same transaction, so a new account always starts
        with the welcome message ready to render.
        """
        try:
            users = metadata.tables["users_dummy"]
            chat_history = metadata.tables["chat_history_dummy"]

            logger.info(
                "request_id: '%s' Signup attempt for username='%s'",
                self.request_id, payload.username,
            )

            async with AsyncSessionLocal() as session:
                existing = await session.execute(
                    select(users.c.id).where(users.c.username == payload.username)
                )
                if existing.scalar() is not None:
                    logger.error(
                        "request_id: '%s' Username '%s' already taken",
                        self.request_id, payload.username,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Username already taken",
                    )

                stmt = (
                    insert(users)
                    .values(
                        username=payload.username,
                        first_name=payload.first_name,
                        last_name=payload.last_name,
                        password_hash=hash_password(payload.password),
                    )
                    .returning(users.c.id)
                )
                result = await session.execute(stmt)
                new_id = int(result.scalar())

                await session.execute(
                    insert(chat_history).values(
                        user_id=new_id,
                        role="assistant",
                        message=get_welcome_message(),
                    )
                )
                await session.commit()

            token, expires_in = create_access_token(user_id=new_id, username=payload.username)
            logger.info(
                "request_id: '%s' User '%s' created with id=%d",
                self.request_id, payload.username, new_id,
            )
            return TokenResponse(
                access_token=token,
                user_id=new_id,
                username=payload.username,
                expires_in=expires_in,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                "request_id: '%s' Error in signup for username='%s': %s",
                self.request_id, payload.username, str(e), exc_info=True,
            )
            raise

    async def login(self, payload: LoginRequest) -> TokenResponse:
        """Verify credentials and return an access token."""
        try:
            users = metadata.tables["users_dummy"]

            logger.info(
                "request_id: '%s' Login attempt for username='%s'",
                self.request_id, payload.username,
            )

            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(users.c.id, users.c.username, users.c.password_hash).where(
                        users.c.username == payload.username
                    )
                )
                row = result.first()

            if row is None or not verify_password(payload.password, row.password_hash):
                logger.error(
                    "request_id: '%s' Invalid credentials for username='%s'",
                    self.request_id, payload.username,
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid username or password",
                )

            token, expires_in = create_access_token(user_id=int(row.id), username=row.username)
            logger.info(
                "request_id: '%s' User '%s' logged in (id=%d)",
                self.request_id, row.username, row.id,
            )
            return TokenResponse(
                access_token=token,
                user_id=int(row.id),
                username=row.username,
                expires_in=expires_in,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                "request_id: '%s' Error in login for username='%s': %s",
                self.request_id, payload.username, str(e), exc_info=True,
            )
            raise
