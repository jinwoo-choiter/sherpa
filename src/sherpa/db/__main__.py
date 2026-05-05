"""CLI: `python -m sherpa.db init` — create schema in the configured SQLite file."""

from __future__ import annotations

import argparse

from sherpa.config import load
from sherpa.db.repo import connect, init_schema


def main() -> None:
    parser = argparse.ArgumentParser(prog="sherpa.db")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="create schema in SHERPA_DB_PATH")
    args = parser.parse_args()

    cfg = load()
    if args.cmd == "init":
        with connect(cfg.db_path) as conn:
            init_schema(conn)
        print(f"Initialized schema at {cfg.db_path}")


if __name__ == "__main__":
    main()
