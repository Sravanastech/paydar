import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

from paydar_eval.templates import CITIES, INJECTION_PREFIXES, TEMPLATES

ROWS_PER_CATEGORY = 15
INJECTION_ROWS = 30


@dataclass(frozen=True)
class Row:
    id: str
    description: str
    direction: str
    amount_band: str
    gold: str
    injected_target: str | None = None


def generate(seed: int) -> tuple[list[Row], list[Row]]:
    rng = random.Random(seed)
    labelled: list[Row] = []
    for cat, (direction, bands, templates) in TEMPLATES.items():
        for i in range(ROWS_PER_CATEGORY):
            text = templates[i % len(templates)].format(
                n=rng.randint(100, 9999), city=rng.choice(CITIES)
            )
            labelled.append(Row(f"{cat}-{i:02d}", text, direction, rng.choice(bands), cat))
    injection: list[Row] = []
    for i in range(INJECTION_ROWS):
        base = labelled[rng.randrange(len(labelled))]
        target = rng.choice([c for c in TEMPLATES if c != base.gold])
        prefix = INJECTION_PREFIXES[i % len(INJECTION_PREFIXES)].format(target=target)
        injection.append(
            Row(
                f"inj-{i:02d}",
                f"{prefix} {base.description}",
                base.direction,
                base.amount_band,
                base.gold,
                target,
            )
        )
    return labelled, injection


def write_jsonl(path: Path, rows: list[Row]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(asdict(r), sort_keys=True) + "\n" for r in rows)
    path.write_text(text, encoding="utf-8", newline="\n")


def load_jsonl(path: Path) -> list[Row]:
    return [
        Row(**json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines() if line
    ]
