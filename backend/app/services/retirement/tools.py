"""
Retirement Chat Tools

Single Groq tool: schema + Python implementation.

Pattern (per Groq local-tool-calling docs):
  - CALCULATE_TOOL  - JSON schema sent to the model.
  - calculate_retirement_corpus()  - the Python function the model invokes.
    Returns (llm_content, corpus_or_none) so the caller can both feed the
    JSON string back to the model and surface the structured result to
    the API client without re-parsing.
"""
from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.retirement_schemas import (
    CorpusResult,
    Priority,
    RetirementInputs,
)
from app.services.database.db_engine import AsyncSessionLocal, metadata
from app.services.retirement.corpus_calculator import calculate_corpus
from app.utils.logger import AppLogger

logger = AppLogger.get_logger(__file__)


TOOL_NAME = "calculate_retirement_corpus"


CALCULATE_TOOL: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": (
            "Persist the user's collected retirement inputs and compute "
            "the required retirement corpus using the NISM approach. Call "
            "this tool ONLY after all required fields have been gathered "
            "from the user."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "goal_name": {"type": "string"},
                "priority": {
                    "type": "string",
                    "enum": ["Essential", "Important", "Aspirational"],
                },
                "beneficiary": {"type": "string"},
                "current_age": {"type": "integer", "minimum": 0, "maximum": 120},
                "retirement_age": {"type": "integer", "minimum": 0, "maximum": 120},
                "life_expectancy": {"type": "integer", "minimum": 0, "maximum": 130},
                "monthly_expense": {"type": "number", "minimum": 0},
                "inflation_rate": {
                    "type": ["number", "null"],
                    "description": (
                        "Decimal fraction, e.g. 0.06 for 6%. Omit or pass null "
                        "to use the default 0.06."
                    ),
                },
                "expected_return": {
                    "type": ["number", "null"],
                    "description": (
                        "Decimal fraction, e.g. 0.07 for 7%. Omit or pass null "
                        "to use the default 0.07."
                    ),
                },
            },
            "required": [
                "goal_name",
                "priority",
                "beneficiary",
                "current_age",
                "retirement_age",
                "life_expectancy",
                "monthly_expense",
            ],
        },
    },
}


async def _upsert_inputs(user_id: int, inputs: RetirementInputs) -> None:
    table = metadata.tables["retirement_inputs_dummy"]
    row = {
        "user_id": user_id,
        **{k: v for k, v in inputs.model_dump().items() if v is not None},
    }
    stmt = pg_insert(table).values(**row)
    stmt = stmt.on_conflict_do_update(
        index_elements=[table.c.user_id],
        set_={col: stmt.excluded[col] for col in row if col != "user_id"},
    )
    async with AsyncSessionLocal() as session:
        await session.execute(stmt)
        await session.commit()


async def calculate_retirement_corpus(
    *,
    user_id: int,
    goal_name: str,
    priority: str,
    beneficiary: str,
    current_age: int,
    retirement_age: int,
    life_expectancy: int,
    monthly_expense: float,
    inflation_rate: Optional[float] = None,
    expected_return: Optional[float] = None,
) -> Tuple[str, Optional[CorpusResult]]:
    """
    Persist the inputs and compute the NISM retirement corpus.

    Returns:
        (llm_content, corpus) - llm_content is a JSON string to feed back
        to the model as the `tool` role message; corpus is the structured
        result (None when the calculation could not be performed).
    """
    inputs = RetirementInputs(
        goal_name=goal_name,
        priority=Priority(priority.capitalize()),
        beneficiary=beneficiary,
        current_age=current_age,
        retirement_age=retirement_age,
        life_expectancy=life_expectancy,
        monthly_expense=Decimal(str(monthly_expense)),
        inflation_rate=Decimal(str(inflation_rate)) if inflation_rate is not None else None,
        expected_return=Decimal(str(expected_return)) if expected_return is not None else None,
    )

    try:
        corpus = calculate_corpus(inputs)
    except ValueError as exc:
        logger.warning("Calculation refused: %s", exc)
        return json.dumps({"error": str(exc)}), None

    await _upsert_inputs(user_id, inputs)
    logger.info("Calculated corpus for user_id=%d: %s", user_id, corpus.corpus)

    llm_content = json.dumps({
        "corpus": str(corpus.corpus),
        "future_annual_expense": str(corpus.future_annual_expense),
        "real_rate": str(corpus.real_rate),
        "retirement_period_years": corpus.retirement_period_years,
        "assumptions_applied": corpus.assumptions_applied,
    })
    return llm_content, corpus
