import argparse
import json
import random
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from paydar_contracts.categories import LLM_CATEGORY_IDS

from paydar_eval.client import OllamaClient
from paydar_eval.dataset import Row, generate, load_jsonl, write_jsonl
from paydar_eval.metrics import CallStat, failed_gates, summarise
from paydar_eval.protocol import MAX_BATCH, Prediction, build_request, parse_response

ChatFn = Callable[[dict[str, Any]], tuple[dict[str, Any], float]]
SUMMARY_KEYS = (
    "accuracy",
    "json_valid_rate",
    "enum_valid_rate",
    "injection_success_rate",
    "p50_row_ms",
    "resident_gb",
    "calibrated_threshold",
    "failed_gates",
)


def run_eval(
    rows: Sequence[Row], chat: ChatFn, model: str, num_ctx: int, batch: int = MAX_BATCH
) -> tuple[list[Prediction | None], list[CallStat]]:
    preds: list[Prediction | None] = []
    calls: list[CallStat] = []
    for start in range(0, len(rows), batch):
        chunk = rows[start : start + batch]
        body, ms = chat(build_request(model, chunk, LLM_CATEGORY_IDS, num_ctx))
        parsed = parse_response(body, len(chunk), LLM_CATEGORY_IDS)
        preds += parsed.predictions
        calls.append(CallStat(len(chunk), ms, parsed.json_ok, parsed.enum_violations))
    return preds, calls


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="paydar-eval")
    sub = parser.add_subparsers(dest="cmd", required=True)
    gen = sub.add_parser("gen", help="write the synthetic labelled and injection sets")
    gen.add_argument("--seed", type=int, default=42)
    gen.add_argument("--out", type=Path, default=Path("evals/categorisation"))
    cat = sub.add_parser("categorise", help="run the ADR-11 categorisation eval")
    cat.add_argument("--model", required=True)
    cat.add_argument("--data", type=Path, default=Path("evals/categorisation"))
    cat.add_argument("--out", type=Path, required=True)
    cat.add_argument("--num-ctx", type=int, default=8192)
    cat.add_argument("--batch", type=int, default=MAX_BATCH)
    cat.add_argument("--base-url", default="http://127.0.0.1:11434")
    args = parser.parse_args(argv)

    if args.cmd == "gen":
        labelled, injection = generate(args.seed)
        write_jsonl(args.out / "labelled.jsonl", labelled)
        write_jsonl(args.out / "injection.jsonl", injection)
        print(f"wrote {len(labelled)} labelled and {len(injection)} injection rows")
        return 0

    rows = load_jsonl(args.data / "labelled.jsonl") + load_jsonl(args.data / "injection.jsonl")
    random.Random(0).shuffle(rows)  # mix categories and injections across batches
    client = OllamaClient(args.base_url)
    preds, calls = run_eval(rows, client.chat, args.model, args.num_ctx, args.batch)
    report = {
        "model": args.model,
        "num_ctx": args.num_ctx,
        "batch": args.batch,
        **summarise(rows, preds, calls, client.resident_bytes(args.model)),
    }
    report["failed_gates"] = failed_gates(report)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in SUMMARY_KEYS}, indent=2))
    return 1 if report["failed_gates"] else 0


def entry() -> None:
    sys.exit(main())
