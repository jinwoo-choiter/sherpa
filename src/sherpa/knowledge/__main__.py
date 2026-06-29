"""CLI: distill candidates, curate (confirm/reject), list entries.

    python -m sherpa.knowledge distill
    python -m sherpa.knowledge confirm <entry-id>
    python -m sherpa.knowledge reject  <entry-id>
    python -m sherpa.knowledge list [--status candidate|active|rejected]
"""

from __future__ import annotations

import argparse
import sys

from sherpa.config import load
from sherpa.knowledge import store


def main() -> None:
    parser = argparse.ArgumentParser(prog="sherpa.knowledge")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("distill", help="create candidate entries from good-cases-only outcomes")
    c = sub.add_parser("confirm", help="promote a candidate to active")
    c.add_argument("entry_id")
    j = sub.add_parser("reject", help="mark a candidate rejected (never injected, never re-proposed)")
    j.add_argument("entry_id")
    ls = sub.add_parser("list", help="list entries")
    ls.add_argument("--status", choices=["candidate", "active", "rejected"], default=None)
    args = parser.parse_args()

    cfg = load()
    if args.cmd == "distill":
        n = store.distill(cfg)
        sys.stdout.write(f"created {n} candidate(s)\n")
    elif args.cmd == "confirm":
        store.set_status(cfg, args.entry_id, "active")
        sys.stdout.write(f"{args.entry_id} -> active\n")
    elif args.cmd == "reject":
        store.set_status(cfg, args.entry_id, "rejected")
        sys.stdout.write(f"{args.entry_id} -> rejected\n")
    elif args.cmd == "list":
        for e in store.listing(cfg, args.status):
            sys.stdout.write(f"{e.id}\t{e.status}\t{e.body[:80].replace(chr(10), ' ')}\n")


if __name__ == "__main__":
    main()
