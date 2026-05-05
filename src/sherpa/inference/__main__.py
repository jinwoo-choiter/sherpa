"""CLI: `python -m sherpa.inference run --pr <id>` — prints body to stdout, never posts."""

from __future__ import annotations

import argparse
import sys

from sherpa.config import load
from sherpa.inference.runner import run


def main() -> None:
    parser = argparse.ArgumentParser(prog="sherpa.inference")
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run inference for a PR; prints body to stdout")
    r.add_argument("--pr", dest="pr_id", required=True)
    r.add_argument("--top-n", dest="top_n", type=int, default=5)
    args = parser.parse_args()

    cfg = load()
    if args.cmd == "run":
        result = run(cfg, args.pr_id, top_n=args.top_n)
        sys.stdout.write(result.body)
        sys.stdout.write("\n")
        sys.stderr.write(f"audit: {result.audit_path}\n")
        sys.stderr.write(f"exemplars: {','.join(result.exemplar_ids) or '(none)'}\n")


if __name__ == "__main__":
    main()
