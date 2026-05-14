"""
Retirement Chatbot Schemas

Pydantic models for the retirement goal chatbot and its supporting auth
endpoints. All datatypes are user-facing (API I/O); table structure lives
in the database itself and is reflected by db_engine.
"""
from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------- #
# Auth                                                                   #
# ---------------------------------------------------------------------- #

class SignupRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
    expires_in: int = Field(..., description="Seconds until the token expires.")


class UserPublic(BaseModel):
    id: int
    username: str
    first_name: str
    last_name: str


# ---------------------------------------------------------------------- #
# Retirement inputs                                                      #
# ---------------------------------------------------------------------- #

class Priority(str, Enum):
    ESSENTIAL = "Essential"
    IMPORTANT = "Important"
    ASPIRATIONAL = "Aspirational"


class RetirementInputs(BaseModel):
    """
    Current state of the 7 collected inputs for a user. Any field may be
    None until the chatbot extracts it.
    """
    goal_name: Optional[str] = None
    priority: Optional[Priority] = None
    beneficiary: Optional[str] = None
    current_age: Optional[int] = Field(default=None, ge=0, le=120)
    retirement_age: Optional[int] = Field(default=None, ge=0, le=120)
    life_expectancy: Optional[int] = Field(default=None, ge=0, le=130)
    monthly_expense: Optional[Decimal] = Field(default=None, ge=0)
    inflation_rate: Optional[Decimal] = Field(default=None, ge=0, le=1)
    expected_return: Optional[Decimal] = Field(default=None, ge=0, le=1)


# ---------------------------------------------------------------------- #
# Chat                                                                   #
# ---------------------------------------------------------------------- #

class ChatRequest(BaseModel):
    user_id: int = Field(..., gt=0)
    message: str = Field(default="", max_length=4000)


class CorpusResult(BaseModel):
    """Computed corpus and the intermediate values used to derive it."""
    future_annual_expense: Decimal
    real_rate: Decimal
    retirement_period_years: int
    corpus: Decimal
    assumptions_applied: dict = Field(
        default_factory=dict,
        description="Defaults the calculator filled in when a user value was missing.",
    )


class ChatHistoryItem(BaseModel):
    id: int
    role: str
    message: str
    created_at: Optional[str] = None


class ChatHistoryResponse(BaseModel):
    messages: list[ChatHistoryItem]


class ChatResponse(BaseModel):
    """
    One assistant turn returned to the frontend.

    `bot_message` is the raw assistant string. The LLM is instructed to
    include a JSON block at the end of its reply with the values
    collected so far; the frontend parses that block to render the live
    bullet list. The backend does not parse it.

    When the LLM fires the calculation tool, `corpus` is populated with
    the NISM result.
    """
    bot_message: str
    corpus: Optional[CorpusResult] = None
