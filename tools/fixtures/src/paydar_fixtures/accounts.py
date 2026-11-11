import random
from datetime import date, timedelta

from paydar_fixtures.model import Account, Txn

MONTHS: tuple[tuple[int, int], ...] = ((2026, 7), (2026, 8), (2026, 9))
OUTFLOWS: tuple[tuple[str, int, int], ...] = (
    ("WHOLEFDS MKT #{n} AUSTIN TX", 2_500, 18_000),
    ("HEB #{n} AUSTIN TX", 1_500, 12_000),
    ("SHELL OIL {n} AUSTIN TX", 3_000, 6_500),
    ("CHIPOTLE {n} AUSTIN TX", 1_100, 3_200),
    ("TARGET T-{n} AUSTIN TX", 1_500, 9_000),
    ("CVS/PHARMACY #{n}", 800, 4_500),
    ("AMC THEATRES {n}", 1_200, 4_000),
)


def month_end(year: int, month: int) -> date:
    first_next = date(year + month // 12, month % 12 + 1, 1)
    return first_next - timedelta(days=1)


class _Builder:
    def __init__(self, prefix: str) -> None:
        self.prefix = prefix
        self.txns: list[Txn] = []

    def add(self, day: date, description: str, cents: int) -> None:
        self.txns.append(
            Txn(day, description, cents, f"{self.prefix}{day:%Y%m%d}{len(self.txns):04d}")
        )

    def random_spend(
        self, rng: random.Random, year: int, month: int, count: int, sign: int
    ) -> None:
        for _ in range(count):
            name, lo, hi = rng.choice(OUTFLOWS)
            day = date(year, month, rng.randint(1, month_end(year, month).day))
            self.add(day, name.format(n=rng.randint(100, 9999)), sign * rng.randint(lo, hi))

    def done(self) -> tuple[Txn, ...]:
        return tuple(sorted(self.txns, key=lambda t: (t.post_date, t.fitid)))


def checking(rng: random.Random, autopay: dict[tuple[int, int], int]) -> Account:
    b = _Builder("CK")
    payday = date(2026, 7, 3)
    while payday <= date(2026, 9, 30):
        b.add(payday, "ACME PAYROLL DIR DEP", 250_000)
        payday += timedelta(days=14)
    for y, m in MONTHS:
        b.add(date(y, m, 1), "PARKVIEW APTS RENT ACH", -180_000)
        b.add(date(y, m, 12), "CITY OF AUSTIN UTIL", -rng.randint(6_000, 14_000))
        b.add(date(y, m, 20), "SYNTHCARD AUTOPAY", -autopay[(y, m)])
        b.random_spend(rng, y, m, 10, sign=-1)
    return Account(
        "synthbank", "synthbank-checking", "checking", "asset", "000123456789", 500_000, b.done()
    )


def credit_card(rng: random.Random, autopay: dict[tuple[int, int], int]) -> Account:
    b = _Builder("CC")
    for y, m in MONTHS:
        b.add(date(y, m, 20), "PAYMENT THANK YOU", -autopay[(y, m)])
        b.random_spend(rng, y, m, 12, sign=1)
    b.add(date(2026, 9, 28), "INTEREST CHARGE PURCHASES", 1_234)
    return Account(
        "synthcard",
        "synthcard-credit_card",
        "credit_card",
        "liability",
        "4111111111111111",
        45_000,
        b.done(),
    )
