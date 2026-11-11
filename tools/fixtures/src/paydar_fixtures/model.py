from dataclasses import dataclass
from datetime import date
from typing import Literal

AccountClass = Literal["asset", "liability"]


@dataclass(frozen=True)
class Txn:
    post_date: date
    description: str
    amount_cents: int  # account perspective: + means the institution-reported balance went up
    fitid: str


@dataclass(frozen=True)
class Account:
    institution: str
    account_id: str
    account_type: str
    account_class: AccountClass
    ofx_acct_id: str
    initial_cents: int
    txns: tuple[Txn, ...]


@dataclass(frozen=True)
class Statement:
    account: Account
    period_start: date
    period_end: date
    opening_cents: int
    txns: tuple[Txn, ...]  # true rows, as the bank computed the balance
    omitted: tuple[Txn, ...] = ()  # true rows missing from the file (broken fixtures)
    tags: tuple[str, ...] = ()

    @property
    def closing_cents(self) -> int:
        return self.opening_cents + sum(t.amount_cents for t in self.txns)

    @property
    def file_txns(self) -> tuple[Txn, ...]:
        return tuple(t for t in self.txns if t not in self.omitted)

    @property
    def expected_delta_cents(self) -> int:
        return sum(t.amount_cents for t in self.omitted)


def slice_statement(account: Account, start: date, end: date, tags: tuple[str, ...]) -> Statement:
    before = sum(t.amount_cents for t in account.txns if t.post_date < start)
    rows = tuple(t for t in account.txns if start <= t.post_date <= end)
    return Statement(account, start, end, account.initial_cents + before, rows, (), tags)
