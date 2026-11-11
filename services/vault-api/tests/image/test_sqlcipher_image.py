"""SQLCipher works on both architectures and the image runs unprivileged (ADR-09, F-41)."""

import os
import re
import subprocess
from pathlib import Path

import pytest

DOCKERFILE = Path(__file__).resolve().parents[2] / "Dockerfile"
PLATFORMS = os.environ.get("PAYDAR_PLATFORMS", "linux/arm64").split(",")
needs_images = pytest.mark.skipif(
    os.environ.get("PAYDAR_IMAGE_TESTS") != "1", reason="set PAYDAR_IMAGE_TESTS=1"
)

ENCRYPT = r"""
import sqlite3, sqlcipher3
path = "/tmp/t.db"
con = sqlcipher3.connect(path)
con.execute("PRAGMA key = \"x'" + "ab" * 32 + "'\"")
con.execute("CREATE TABLE t (v TEXT)")
con.execute("INSERT INTO t VALUES ('canary-secret')")
con.commit()
con.close()
raw = open(path, "rb").read()
assert not raw.startswith(b"SQLite format 3"), "plaintext header"
assert b"canary-secret" not in raw, "plaintext row"
try:
    sqlite3.connect(path).execute("SELECT * FROM t").fetchall()
except sqlite3.DatabaseError:
    print("encrypted")
else:
    raise SystemExit("readable without key")
"""


def _arg(name: str) -> str:
    match = re.search(rf"^ARG {name}=(\S+)$", DOCKERFILE.read_text(), re.MULTILINE)
    assert match, f"ARG {name} missing"
    return match.group(1)


def _run(platform: str, *cmd: str) -> subprocess.CompletedProcess[str]:
    tag = f"paydar/vault-api:dev-{platform.split('/')[1]}"
    return subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--platform",
            platform,
            "--read-only",
            "--tmpfs",
            "/tmp",  # noqa: S108
            tag,
            *cmd,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_dockerfile_pins_are_filled() -> None:
    assert "REPLACE_" not in DOCKERFILE.read_text()
    assert "@sha256:" in _arg("PYTHON_IMAGE")
    assert re.fullmatch(r"[0-9a-f]{64}", _arg("SQLCIPHER_SHA256"))


@pytest.mark.image
@needs_images
@pytest.mark.parametrize("platform", PLATFORMS)
def test_image_reports_pinned_sqlcipher_version(platform: str) -> None:
    code = "import sqlcipher3; c = sqlcipher3.connect(':memory:'); print(c.execute('PRAGMA cipher_version').fetchone()[0])"
    result = _run(platform, "python", "-c", code)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().startswith(_arg("SQLCIPHER_VERSION"))


@pytest.mark.image
@needs_images
@pytest.mark.parametrize("platform", PLATFORMS)
def test_image_encrypts(platform: str) -> None:
    result = _run(platform, "python", "-c", ENCRYPT)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "encrypted"


@pytest.mark.image
@needs_images
@pytest.mark.parametrize("platform", PLATFORMS)
def test_image_runs_as_uid_10001(platform: str) -> None:
    assert _run(platform, "id", "-u").stdout.strip() == "10001"


@pytest.mark.image
@needs_images
@pytest.mark.parametrize("platform", PLATFORMS)
def test_image_compile_options(platform: str) -> None:
    code = (
        "import sqlcipher3; c = sqlcipher3.connect(':memory:'); "
        "print('\\n'.join(r[0] for r in c.execute('PRAGMA compile_options').fetchall()))"
    )
    result = _run(platform, "python", "-c", code)
    assert result.returncode == 0, result.stderr
    options = result.stdout.split()
    assert "TEMP_STORE=3" in options, options
    assert "HAS_CODEC" in options, options


@pytest.mark.image
@needs_images
@pytest.mark.parametrize("platform", PLATFORMS)
def test_binding_links_pinned_library(platform: str) -> None:
    code = (
        "import glob, subprocess, sqlcipher3; "
        "so = glob.glob(sqlcipher3.__path__[0] + '/_sqlite3*.so')[0]; "
        "print(subprocess.run(['ldd', so], capture_output=True, text=True).stdout)"
    )
    result = _run(platform, "python", "-c", code)
    assert result.returncode == 0, result.stderr
    assert "/opt/sqlcipher/lib/libsqlite3" in result.stdout, result.stdout
