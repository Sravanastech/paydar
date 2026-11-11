import json
import time
import urllib.request
from typing import Any


class OllamaClient:
    """Minimal Ollama HTTP client. Loopback only: eval traffic never leaves the host."""

    def __init__(self, base_url: str = "http://127.0.0.1:11434", timeout_s: float = 600.0) -> None:
        if not base_url.startswith(("http://127.0.0.1:", "http://localhost:")):
            raise ValueError("Ollama base_url must be loopback")
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    def chat(self, payload: dict[str, Any]) -> tuple[dict[str, Any], float]:
        request = urllib.request.Request(  # noqa: S310 - loopback enforced in __init__
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        start = time.perf_counter()
        with urllib.request.urlopen(request, timeout=self.timeout_s) as resp:  # noqa: S310 - loopback enforced
            body: dict[str, Any] = json.loads(resp.read())
        return body, (time.perf_counter() - start) * 1000

    def resident_bytes(self, model: str) -> int:
        with urllib.request.urlopen(f"{self.base_url}/api/ps", timeout=10) as resp:  # noqa: S310
            models = json.loads(resp.read()).get("models", [])
        return sum(
            int(m.get("size", 0)) for m in models if model in (m.get("name"), m.get("model"))
        )
