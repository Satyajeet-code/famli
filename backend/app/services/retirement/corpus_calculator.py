"""
NISM Retirement Corpus Calculator

Implements the NISM-approach corpus calculation from the spec:

    Step 1: Future Annual Expense = Current Annual Expense * (1 + i)^n
            where n = retirement_age - current_age, i = inflation

    Step 2: Real Rate r = (1 + return_during_retirement) / (1 + inflation) - 1

    Step 3: Corpus = Future Annual Expense
                     * ((1 - (1 + r)^-p) / r)
                     * (1 + r)
            where p = retirement_period = life_expectancy - retirement_age

The (1 + r) multiplier accounts for annuity-due (expenses drawn at the
start of each retirement year), matching the spec's worked example.

Defaults applied when an input is missing:
    inflation_rate   -> 0.06 (6%)
    expected_return  -> 0.07 (7%)
    life_expectancy  -> 80

These defaults come from the spec's Assumptions section.
"""
from __future__ import annotations

from decimal import Decimal, getcontext

from app.models.retirement_schemas import CorpusResult, RetirementInputs

# Increase precision so intermediate exponents don't lose accuracy.
getcontext().prec = 28


DEFAULT_INFLATION = Decimal("0.06")
DEFAULT_RETURN = Decimal("0.07")
DEFAULT_LIFE_EXPECTANCY = 80


REQUIRED_USER_FIELDS = ("current_age", "retirement_age", "monthly_expense")


def is_ready_to_calculate(inputs: RetirementInputs) -> bool:
    """True once we have enough user-provided data to run the calculation."""
    return all(getattr(inputs, field) is not None for field in REQUIRED_USER_FIELDS)


def calculate_corpus(inputs: RetirementInputs) -> CorpusResult:
    """
    Run the NISM corpus calculation.

    Raises:
        ValueError: required fields missing, or retirement_age <= current_age,
                    or life_expectancy <= retirement_age.
    """
    missing = [f for f in REQUIRED_USER_FIELDS if getattr(inputs, f) is None]
    if missing:
        raise ValueError(f"Missing required fields for calculation: {missing}")

    inflation = Decimal(inputs.inflation_rate if inputs.inflation_rate is not None else DEFAULT_INFLATION)
    expected_return = Decimal(inputs.expected_return if inputs.expected_return is not None else DEFAULT_RETURN)
    life_expectancy = int(inputs.life_expectancy if inputs.life_expectancy is not None else DEFAULT_LIFE_EXPECTANCY)

    current_age = int(inputs.current_age)
    retirement_age = int(inputs.retirement_age)
    monthly_expense = Decimal(inputs.monthly_expense)

    if retirement_age <= current_age:
        raise ValueError("retirement_age must be greater than current_age")
    if life_expectancy <= retirement_age:
        raise ValueError("life_expectancy must be greater than retirement_age")

    n_years_to_retire = retirement_age - current_age
    retirement_period = life_expectancy - retirement_age

    current_annual_expense = monthly_expense * Decimal(12)

    # Step 1: Future Annual Expense at retirement
    inflation_factor = (Decimal(1) + inflation) ** n_years_to_retire
    future_annual_expense = current_annual_expense * inflation_factor

    # Step 2: Real Rate of Return
    real_rate = (Decimal(1) + expected_return) / (Decimal(1) + inflation) - Decimal(1)

    # Step 3: Corpus (annuity-due present value at retirement)
    discount_factor = (Decimal(1) + real_rate) ** (-retirement_period)
    annuity_factor = (Decimal(1) - discount_factor) / real_rate
    corpus = future_annual_expense * annuity_factor * (Decimal(1) + real_rate)

    return CorpusResult(
        future_annual_expense=future_annual_expense.quantize(Decimal("0.01")),
        real_rate=real_rate.quantize(Decimal("0.00000001")),
        retirement_period_years=retirement_period,
        corpus=corpus.quantize(Decimal("0.01")),
    )
