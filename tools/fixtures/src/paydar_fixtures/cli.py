import argparse
from pathlib import Path

from paydar_fixtures.build import write_all


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate deterministic synthetic statements.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path("fixtures"))
    args = parser.parse_args()
    manifest = write_all(args.out, args.seed)
    print(f"wrote {len(manifest['statements'])} statements to {args.out}")
