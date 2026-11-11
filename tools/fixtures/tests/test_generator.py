import csv
import io
import re
from pathlib import Path

from paydar_fixtures.build import write_all

REPO_ROOT = Path(__file__).resolve().parents[3]
LONG_DIGITS = re.compile(r"(?<!\d)\d{13,19}(?!\d)")
TEST_PREFIXES = ("4111", "5555", "3782")


def _files(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def _cents(text: str) -> int:
    neg = text.startswith("-")
    whole, frac = text.lstrip("-").split(".")
    value = int(whole) * 100 + int(frac)
    return -value if neg else value


def _file_total(path: Path, fmt: str, account_class: str) -> int:
    text = path.read_text()
    if fmt == "csv":
        return sum(_cents(r["Amount"]) for r in csv.DictReader(io.StringIO(text)))
    total = sum(_cents(a) for a in re.findall(r"<TRNAMT>([-0-9.]+)</TRNAMT>", text))
    return -total if account_class == "liability" else total


def _luhn(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch) * (2 if i % 2 else 1)
        total += d - 9 if d > 9 else d
    return total % 10 == 0


def test_generator_is_deterministic(tmp_path: Path) -> None:
    write_all(tmp_path / "a", seed=42)
    write_all(tmp_path / "b", seed=42)
    assert _files(tmp_path / "a") == _files(tmp_path / "b")


def test_committed_fixtures_are_current(tmp_path: Path) -> None:
    write_all(tmp_path, seed=42)
    assert _files(tmp_path) == _files(REPO_ROOT / "fixtures")


def test_manifest_balances_hold_by_construction(tmp_path: Path) -> None:
    for e in write_all(tmp_path, seed=42)["statements"]:
        assert e["opening_cents"] + e["credits_cents"] - e["debits_cents"] == e["closing_cents"]


def test_file_rows_differ_from_truth_only_by_expected_delta(tmp_path: Path) -> None:
    for e in write_all(tmp_path, seed=42)["statements"]:
        total = _file_total(tmp_path / str(e["path"]), str(e["format"]), str(e["account_class"]))
        assert total + e["expected_delta_cents"] == e["closing_cents"] - e["opening_cents"], e[
            "path"
        ]


def test_broken_fixtures_declare_expected_delta(tmp_path: Path) -> None:
    broken = [e for e in write_all(tmp_path, seed=42)["statements"] if "broken" in e["tags"]]
    assert broken and all(e["expected_delta_cents"] != 0 for e in broken)


def test_required_families_present(tmp_path: Path) -> None:
    tags = {t for e in write_all(tmp_path, seed=42)["statements"] for t in e["tags"]}
    assert {"asset", "liability", "broken", "overlap", "cross_format"} <= tags


def test_fixture_card_numbers_use_test_ranges(tmp_path: Path) -> None:
    write_all(tmp_path, seed=42)
    runs = [
        r for p in tmp_path.rglob("*") if p.is_file() for r in LONG_DIGITS.findall(p.read_text())
    ]
    luhn_runs = [r for r in runs if _luhn(r)]
    assert luhn_runs, "expected the synthetic card number to appear"
    assert all(r.startswith(TEST_PREFIXES) for r in luhn_runs)


def test_fixtures_contain_no_owner_blocklist_terms(tmp_path: Path) -> None:
    write_all(tmp_path, seed=42)
    terms = [
        t.lower()
        for t in (Path(__file__).parent / "sample_blocklist.txt").read_text().split("\n")
        if t
    ]
    for p in tmp_path.rglob("*"):
        if p.is_file():
            assert [t for t in terms if t in p.read_text().lower()] == [], p
