import json
import os
from pathlib import Path
from typing import Any

import pytest
from paydar_contracts.categories import LLM_CATEGORY_IDS
from paydar_eval.cli import run_eval
from paydar_eval.client import OllamaClient
from paydar_eval.dataset import generate, write_jsonl
from paydar_eval.metrics import GATES, failed_gates, summarise
from paydar_eval.protocol import Prediction, build_request, parse_response

REPO_ROOT = Path(__file__).resolve().parents[3]
LABELLED, INJECTION = generate(42)
ROWS = [*LABELLED, *INJECTION]
GOLD = {r.description: r.gold for r in ROWS}
TARGET = {r.description: r.injected_target for r in INJECTION}


def _body(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"message": {"content": json.dumps({"items": items})}}


def _stub(follow_injection: bool):
    def chat(payload: dict[str, Any]) -> tuple[dict[str, Any], float]:
        data = payload["messages"][1]["content"].removeprefix("<<<DATA\n").removesuffix("\nDATA>>>")
        txs = json.loads(data)["transactions"]
        items = []
        for t in txs:
            cat = TARGET.get(t["description"]) if follow_injection else None
            items.append(
                {"i": t["i"], "category": cat or GOLD[t["description"]], "confidence": 0.99}
            )
        return _body(items), 100.0 * len(txs)

    return chat


def test_dataset_sizes_and_coverage() -> None:
    assert len(LABELLED) >= 300 and len(INJECTION) >= 30
    assert {r.gold for r in LABELLED} == set(LLM_CATEGORY_IDS) - {"uncategorized"}
    assert all(r.injected_target not in (None, r.gold) for r in INJECTION)


def test_dataset_is_deterministic_and_committed(tmp_path: Path) -> None:
    assert generate(42) == (LABELLED, INJECTION)
    write_jsonl(tmp_path / "labelled.jsonl", LABELLED)
    write_jsonl(tmp_path / "injection.jsonl", INJECTION)
    committed = REPO_ROOT / "evals" / "categorisation"
    for name in ("labelled.jsonl", "injection.jsonl"):
        assert (tmp_path / name).read_bytes() == (committed / name).read_bytes()


def test_request_enforces_adr10_shape() -> None:
    req = build_request("m", LABELLED[:3], LLM_CATEGORY_IDS, 8192)
    assert req["think"] is False and req["stream"] is False
    assert req["options"] == {"temperature": 0, "seed": 7, "num_ctx": 8192}
    item = req["format"]["properties"]["items"]["items"]
    assert item["properties"]["category"]["enum"] == list(LLM_CATEGORY_IDS)
    assert item["properties"]["i"]["maximum"] == 2
    user = req["messages"][1]["content"]
    assert user.startswith("<<<DATA\n") and user.endswith("\nDATA>>>")


def test_request_rejects_oversized_batch() -> None:
    with pytest.raises(ValueError):
        build_request("m", LABELLED[:26], LLM_CATEGORY_IDS, 8192)


def test_parse_counts_enum_violation_and_skips_bad_rows() -> None:
    body = _body(
        [
            {"i": 0, "category": "groceries", "confidence": 0.9},
            {"i": 1, "category": "not_a_category", "confidence": 0.9},
            {"i": 7, "category": "travel", "confidence": 0.5},
        ]
    )
    parsed = parse_response(body, 2, LLM_CATEGORY_IDS)
    assert parsed.json_ok and parsed.enum_violations == 1
    assert parsed.predictions == [Prediction("groceries", 0.9), None]


def test_parse_marks_invalid_json() -> None:
    parsed = parse_response({"message": {"content": "not json"}}, 2, LLM_CATEGORY_IDS)
    assert not parsed.json_ok and parsed.predictions == [None, None]


def test_perfect_stub_passes_all_gates() -> None:
    preds, calls = run_eval(ROWS, _stub(follow_injection=False), "m", 8192)
    report = summarise(
        ROWS, preds, calls, ps_size_bytes=6_000_000_000, ps_size_vram_bytes=6_000_000_000
    )
    assert failed_gates(report) == []
    assert report["calibrated_threshold"] == 0.5


def test_gates_catch_injection_success() -> None:
    preds, calls = run_eval(ROWS, _stub(follow_injection=True), "m", 8192)
    report = summarise(
        ROWS, preds, calls, ps_size_bytes=6_000_000_000, ps_size_vram_bytes=6_000_000_000
    )
    assert report["injection_success_rate"] == 1.0
    assert any(f.startswith("injection_success_rate") for f in failed_gates(report))


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:@evil.example",
        "http://localhost:@evil.example",
        "http://user@127.0.0.1:11434",
        "https://127.0.0.1:11434",
        "http://10.0.0.5:11434",
        "http://127.0.0.1",
    ],
)
def test_client_refuses_non_loopback(url: str) -> None:
    with pytest.raises(ValueError):
        OllamaClient(url)


@pytest.mark.parametrize(
    "url", ["http://127.0.0.1:11434", "http://localhost:11434", "http://[::1]:11434"]
)
def test_client_accepts_loopback(url: str) -> None:
    assert OllamaClient(url).base_url == url


def test_client_resident_requires_loaded_model(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OllamaClient()

    class _Resp:
        def __init__(self, data: dict[str, Any]) -> None:
            self.data = data

        def __enter__(self) -> "_Resp":
            return self

        def __exit__(self, *a: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(self.data).encode()

    ps = {"models": [{"name": "m", "model": "m", "size": 5, "size_vram": 4}]}
    monkeypatch.setattr(client._opener, "open", lambda *a, **k: _Resp(ps))
    assert client.resident_bytes("m") == (5, 4)
    with pytest.raises(RuntimeError):
        client.resident_bytes("other")


def test_memory_is_not_gated_automatically() -> None:
    """ADR-11: memory is measured manually with macOS `footprint`, not from /api/ps."""
    assert not any("resident" in k or "ps_size" in k for k in GATES)


def test_coverage_gate_catches_dropped_rows() -> None:
    inner = _stub(follow_injection=False)

    def lossy(payload: dict[str, Any]) -> tuple[dict[str, Any], float]:
        body, ms = inner(payload)
        items = json.loads(body["message"]["content"])["items"]
        return _body(items[:-1]), ms

    preds, calls = run_eval(ROWS, lossy, "m", 8192)
    report = summarise(ROWS, preds, calls, ps_size_bytes=1, ps_size_vram_bytes=1)
    assert report["coverage"] < 1.0
    assert any(f.startswith("coverage") for f in failed_gates(report))


def test_per_row_output_when_requested() -> None:
    preds, calls = run_eval(ROWS, _stub(follow_injection=False), "m", 8192)
    report = summarise(ROWS, preds, calls, ps_size_bytes=1, ps_size_vram_bytes=1, per_row=True)
    first = report["rows"][0]
    assert set(first) == {"id", "gold", "predicted", "confidence", "injected_target"}
    assert len(report["rows"]) == len(ROWS)
    plain = summarise(ROWS, preds, calls, ps_size_bytes=1, ps_size_vram_bytes=1)
    assert "rows" not in plain


@pytest.mark.live_llm
@pytest.mark.enable_socket
@pytest.mark.skipif(os.environ.get("PAYDAR_LIVE_LLM") != "1", reason="set PAYDAR_LIVE_LLM=1")
def test_live_batch_is_schema_valid_without_thinking() -> None:
    model = os.environ.get("OLLAMA_MODEL", "gemma4:e4b-it-qat")
    body, _ = OllamaClient().chat(build_request(model, LABELLED[:5], LLM_CATEGORY_IDS, 8192))
    parsed = parse_response(body, 5, LLM_CATEGORY_IDS)
    assert parsed.json_ok and parsed.enum_violations == 0
    assert not body.get("message", {}).get("thinking")
