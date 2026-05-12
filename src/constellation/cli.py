from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="constellation")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run the restriction-rewriting pipeline")
    run.add_argument("corpus", type=Path)
    run.add_argument("--output", type=Path, default=None)
    run.add_argument("--force", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        output = args.output or Path("runs") / f"{args.corpus.name}_run"
        summary = run_pipeline(args.corpus, output, force=args.force)
        print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

