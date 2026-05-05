"""CLI: `python -m sherpa.ingester poll <owner/repo>`."""

from __future__ import annotations

import argparse

from sherpa.config import load
from sherpa.ingester.poller import poll_repo


def main() -> None:
    parser = argparse.ArgumentParser(prog="sherpa.ingester")
    sub = parser.add_subparsers(dest="cmd", required=True)
    poll = sub.add_parser("poll", help="ingest a repo's PRs/comments/diffs")
    poll.add_argument("repo", help="owner/repo")
    args = parser.parse_args()

    cfg = load()
    if args.cmd == "poll":
        owner, _, name = args.repo.partition("/")
        if not owner or not name:
            raise SystemExit("repo must be 'owner/name'")
        result = poll_repo(cfg, owner, name)
        print(
            f"Polled {result.repo}: "
            f"{result.prs_seen} PRs, {result.comments_seen} comments, {result.diffs_seen} diffs"
        )


if __name__ == "__main__":
    main()
