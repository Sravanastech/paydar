"""Every relative Markdown link in the local docs resolves (ADR-15 moves must not break docs). Skipped when the docs repo is absent."""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
# Local docs repo: README.md, docs/, skills/ (absent in CI and fresh clones).
DOCS_ROOT = REPO_ROOT.parent
LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")


def _markdown_files() -> list[Path]:
    files = [DOCS_ROOT / "README.md"]
    for pattern in ("docs/**/*.md", "skills/**/*.md"):
        files += [p for p in DOCS_ROOT.glob(pattern) if "archive" not in p.parts]
    return [f for f in files if f.exists()]


@pytest.mark.skipif(not (DOCS_ROOT / "docs").is_dir(), reason="local docs repo not present")
def test_relative_markdown_links_resolve() -> None:
    broken = []
    for md in _markdown_files():
        for target in LINK.findall(md.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            if not (md.parent / target).exists():
                broken.append(f"{md.relative_to(DOCS_ROOT)} -> {target}")
    assert broken == []
