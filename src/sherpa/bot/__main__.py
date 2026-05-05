"""CLI: `python -m sherpa.bot post --pr <owner/repo#number> --body-file <path>`."""

from __future__ import annotations

import argparse
from pathlib import Path

from sherpa.config import load
from sherpa.bot.poster import post


def main() -> None:
    parser = argparse.ArgumentParser(prog="sherpa.bot")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("post", help="post (or update) a pre-flight comment")
    p.add_argument("--pr", required=True, help="owner/repo#number")
    p.add_argument("--body-file", required=True, help="path to comment body text")
    args = parser.parse_args()

    cfg = load()
    if args.cmd == "post":
        target, _, num = args.pr.partition("#")
        owner, _, repo = target.partition("/")
        if not owner or not repo or not num:
            raise SystemExit("--pr must look like 'owner/repo#123'")
        body = Path(args.body_file).read_text(encoding="utf-8")
        result = post(cfg, owner, repo, int(num), body)
        print(f"{result.action} comment id={result.comment_id}")


if __name__ == "__main__":
    main()
