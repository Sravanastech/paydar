import re
from pathlib import Path

import pytest
from paydar_contracts.categories import LLM_CATEGORY_IDS, CategoryId

# The design docs live in the parent (local-only) docs repo and are NOT present in CI.
SPEC = Path(__file__).resolve().parents[4] / "docs" / "02-TECHNICAL-DESIGN-SPEC.md"

FROZEN_IDS = sorted(
    [
        "uncategorized",
        "income_paycheck",
        "housing_rent",
        "restaurants_dining",
        "groceries",
        "parking_transit",
        "utilities_bills",
        "savings_investments",
        "loans_debt_payment",
        "subscriptions",
        "shopping_lifestyle",
        "internal_transfer",
        "fees_interest",
        "healthcare",
        "insurance",
        "taxes",
        "travel",
        "personal_care",
        "gifts_donations",
        "education_childcare",
        "entertainment",
        "investment_income",
        "rewards_cashback",
    ]
)


def _seeded_ids() -> list[str]:
    block = SPEC.read_text().split("INSERT INTO categories", 1)[1].split(";", 1)[0]
    return re.findall(r"^\s*\('([a-z_]+)',", block, re.MULTILINE)


def test_category_ids_frozen() -> None:
    """Always runs (CI has no docs): the 23 ids are frozen here; changing them is a deliberate edit."""
    assert sorted(c.value for c in CategoryId) == FROZEN_IDS


def test_category_ids_match_doc02_seed() -> None:
    if not SPEC.exists():
        pytest.skip("design docs not present")
    assert sorted(c.value for c in CategoryId) == sorted(_seeded_ids())


def test_llm_ids_exclude_transfer_and_debt_payment() -> None:
    assert "internal_transfer" not in LLM_CATEGORY_IDS
    assert "loans_debt_payment" not in LLM_CATEGORY_IDS
    assert len(LLM_CATEGORY_IDS) == len(CategoryId) - 2
