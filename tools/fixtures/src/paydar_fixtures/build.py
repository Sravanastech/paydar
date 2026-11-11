import dataclasses
import json
import random
from datetime import date
from pathlib import Path

from paydar_fixtures.accounts import MONTHS, checking, credit_card, month_end
from paydar_fixtures.model import Statement, slice_statement
from paydar_fixtures.writers import to_csv, to_ofx

Entry = tuple[str, str, Statement]


def statements(seed: int) -> list[Entry]:
    rng = random.Random(seed)
    autopay = {ym: rng.randint(30_000, 90_000) for ym in MONTHS}
    ck, cc = checking(rng, autopay), credit_card(rng, autopay)
    out: list[Entry] = []
    for y, m in MONTHS:
        start, end, ym = date(y, m, 1), month_end(y, m), f"{y}-{m:02d}"
        s = slice_statement(ck, start, end, ("asset", "cross_format"))
        out += [
            (f"synthetic/synthbank/checking/{ym}.ofx", "ofx", s),
            (f"synthetic/synthbank/checking/{ym}.csv", "csv", s),
            (
                f"synthetic/synthcard/credit_card/{ym}.ofx",
                "ofx",
                slice_statement(cc, start, end, ("liability",)),
            ),
        ]
    sep = slice_statement(ck, date(2026, 9, 1), date(2026, 9, 30), ("asset", "broken"))
    victim = sep.txns[rng.randrange(len(sep.txns))]
    out.append(
        (
            "synthetic/synthbank/checking/2026-09-broken.csv",
            "csv",
            dataclasses.replace(sep, omitted=(victim,)),
        )
    )
    out.append(
        (
            "synthetic/synthbank/checking/2026-08-15_2026-09-14-overlap.ofx",
            "ofx",
            slice_statement(ck, date(2026, 8, 15), date(2026, 9, 14), ("asset", "overlap")),
        )
    )
    return out


def _entry(path: str, fmt: str, s: Statement) -> dict[str, object]:
    return {
        "path": path,
        "format": fmt,
        "institution": s.account.institution,
        "account_id": s.account.account_id,
        "account_class": s.account.account_class,
        "period_start": s.period_start.isoformat(),
        "period_end": s.period_end.isoformat(),
        "opening_cents": s.opening_cents,
        "closing_cents": s.closing_cents,
        "credits_cents": sum(t.amount_cents for t in s.txns if t.amount_cents > 0),
        "debits_cents": -sum(t.amount_cents for t in s.txns if t.amount_cents < 0),
        "file_row_count": len(s.file_txns),
        "expected_delta_cents": s.expected_delta_cents,
        "tags": sorted(s.tags),
    }


def write_all(out: Path, seed: int) -> dict[str, list[dict[str, object]]]:
    manifest: dict[str, list[dict[str, object]]] = {"statements": []}
    for path, fmt, s in statements(seed):
        target = out / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(to_csv(s) if fmt == "csv" else to_ofx(s), encoding="utf-8", newline="\n")
        manifest["statements"].append(_entry(path, fmt, s))
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    return manifest
