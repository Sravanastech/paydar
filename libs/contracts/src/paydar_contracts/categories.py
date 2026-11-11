"""System category ids. Source of truth: doc 02 categories seed (ADR-05)."""

from enum import StrEnum


class CategoryId(StrEnum):
    UNCATEGORIZED = "uncategorized"
    INCOME_PAYCHECK = "income_paycheck"
    HOUSING_RENT = "housing_rent"
    RESTAURANTS_DINING = "restaurants_dining"
    GROCERIES = "groceries"
    PARKING_TRANSIT = "parking_transit"
    UTILITIES_BILLS = "utilities_bills"
    SAVINGS_INVESTMENTS = "savings_investments"
    LOANS_DEBT_PAYMENT = "loans_debt_payment"
    SUBSCRIPTIONS = "subscriptions"
    SHOPPING_LIFESTYLE = "shopping_lifestyle"
    INTERNAL_TRANSFER = "internal_transfer"
    FEES_INTEREST = "fees_interest"
    HEALTHCARE = "healthcare"
    INSURANCE = "insurance"
    TAXES = "taxes"
    TRAVEL = "travel"
    PERSONAL_CARE = "personal_care"
    GIFTS_DONATIONS = "gifts_donations"
    EDUCATION_CHILDCARE = "education_childcare"
    ENTERTAINMENT = "entertainment"
    INVESTMENT_INCOME = "investment_income"
    REWARDS_CASHBACK = "rewards_cashback"


NOT_LLM_ASSIGNABLE = frozenset({CategoryId.INTERNAL_TRANSFER, CategoryId.LOANS_DEBT_PAYMENT})
LLM_CATEGORY_IDS: tuple[str, ...] = tuple(
    c.value for c in CategoryId if c not in NOT_LLM_ASSIGNABLE
)
