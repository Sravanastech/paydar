import json
import time
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse every redirect: eval traffic must stay on the loopback endpoint."""

    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def _validate_loopback(base_url: str) -> None:
    try:
        parts = urlparse(base_url)
        port = parts.port
        host = parts.hostname
    except ValueError as exc:
        raise ValueError("Ollama base_url is malformed") from exc
    if (
        parts.scheme != "http"
        or host not in LOOPBACK_HOSTS
        or parts.username is not None
        or parts.password is not None
        or port is None
    ):
        raise ValueError("Ollama base_url must be http://<loopback>:<port> without credentials")


class OllamaClient:
    """Minimal Ollama HTTP client. Loopback only: eval traffic never leaves the host."""

    def __init__(self, base_url: str = "http://127.0.0.1:11434", timeout_s: float = 600.0) -> None:
        _validate_loopback(base_url)
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        # No proxies (env proxies could route loopback traffic off-host), no redirects.
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect)

    def chat(self, payload: dict[str, Any]) -> tuple[dict[str, Any], float]:
        request = urllib.request.Request(  # noqa: S310 - loopback validated in __init__
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        start = time.perf_counter()
        with self._opener.open(request, timeout=self.timeout_s) as resp:
            body: dict[str, Any] = json.loads(resp.read())
        return body, (time.perf_counter() - start) * 1000

    def resident_bytes(self, model: str) -> tuple[int, int]:
        """Return (size, size_vram) from /api/ps for the loaded model. Informational only."""
        with self._opener.open(f"{self.base_url}/api/ps", timeout=10) as resp:
            models = json.loads(resp.read()).get("models", [])
        for m in models:
            if model in (m.get("name"), m.get("model")):
                return int(m.get("size", 0)), int(m.get("size_vram", 0))
        raise RuntimeError(f"model {model!r} is not loaded according to /api/ps")
