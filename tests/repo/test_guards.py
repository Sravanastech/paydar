"""Money-type guard, import contracts and Hypothesis profiles (doc 06 ground rules 2 and 4)."""

import ast
import subprocess
from pathlib import Path

from hypothesis import settings

REPO_ROOT = Path(__file__).resolve().parents[2]
MONEY_PACKAGES = ["services/vault-api/src/paydar/ledger", "services/vault-api/src/paydar/insights"]
BANNED_NAMES = {"float", "Decimal"}
BANNED_MODULES = {"decimal", "math", "fractions"}


def find_money_floats(root: Path) -> list[str]:
    """Return 'file:line: reason' for every float/Decimal use under root."""
    problems: list[str] = []
    for path in sorted(root.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
            line = getattr(node, "lineno", 0)
            if isinstance(node, ast.Constant) and isinstance(node.value, float):
                problems.append(f"{path}:{line}: float literal")
            elif isinstance(node, ast.Name) and node.id in BANNED_NAMES:
                problems.append(f"{path}:{line}: {node.id}")
            elif isinstance(node, ast.Import | ast.ImportFrom):
                names = (
                    [a.name for a in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module or ""]
                )
                problems += [
                    f"{path}:{line}: import {n}" for n in names if n.split(".")[0] in BANNED_MODULES
                ]
            elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                problems.append(f"{path}:{line}: true division (use // or divmod)")
    return problems


def test_scanner_detects_planted_float(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text("import decimal\nx = 1.5\ny = float(2)\nz = 3 / 2\n")
    assert len(find_money_floats(tmp_path)) == 4


def test_money_packages_have_no_float() -> None:
    problems = [p for pkg in MONEY_PACKAGES for p in find_money_floats(REPO_ROOT / pkg)]
    assert problems == []


def test_import_contracts_hold() -> None:
    result = subprocess.run(
        ["lint-imports"], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_hypothesis_ci_profile_registered() -> None:
    profile = settings.get_profile("ci")
    assert profile.max_examples == 500
    assert profile.derandomize is True
