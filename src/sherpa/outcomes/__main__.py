"""CLI: `python -m sherpa.outcomes recompute [--pr <id>]`."""

from __future__ import annotations

import argparse

from sherpa.config import load
from sherpa.outcomes.runner import recompute_all, recompute_pr


def main() -> None:
    parser = argparse.ArgumentParser(prog="sherpa.outcomes")
    sub = parser.add_subparsers(dest="cmd", required=True)
    rc = sub.add_parser("recompute", help="recompute comment_outcomes")
    rc.add_argument("--pr", dest="pr_id", help="GitHub PR node id; omit to recompute all")
    args = parser.parse_args()

    cfg = load()
    if args.cmd == "recompute":
        result = recompute_pr(cfg, args.pr_id) if args.pr_id else recompute_all(cfg)
        print(
            f"Classified {result.comments_classified} comments — "
            f"addressed={result.addressed}, discussed={result.discussed}, "
            f"dismissed={result.dismissed}, ignored={result.ignored}"
        )


if __name__ == "__main__":
    main()
