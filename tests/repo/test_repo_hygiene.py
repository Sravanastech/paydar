"""Secrets and financial data can never be committed (ADR-09, doc 06 ground rule 3)."""

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_IGNORES = [
    ".secrets/",
    "*.db",
    "*.db-wal",
    "*.db-shm",
    "Financials/",
    ".env",
    ".env.secret",
    "vault.keyfile.json",
    "backups/",
    ".DS_Store",
    "evals/private/",
    "docs/",
]


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )


def test_gitignore_covers_sensitive_paths() -> None:
    lines = {line.strip() for line in (REPO_ROOT / ".gitignore").read_text().splitlines()}
    assert [p for p in REQUIRED_IGNORES if p not in lines] == []


def test_no_tracked_file_matches_sensitive_patterns() -> None:
    out = _git("ls-files", "--cached", "--ignored", "--exclude-standard").stdout.split()
    assert out == []


def test_sample_sensitive_paths_are_ignored() -> None:
    samples = [".env", "x/vault.db", ".secrets/token", "evals/private/r.json"]
    out = _git("check-ignore", "--no-index", *samples).stdout.split()
    assert sorted(out) == sorted(samples)
