"""CLI: `python -m sherpa.rag build` — build the seed index from current SQLite."""

from __future__ import annotations

import argparse

from sherpa.config import load
from sherpa.rag.indexer import build


def main() -> None:
    parser = argparse.ArgumentParser(prog="sherpa.rag")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build", help="rebuild the seed RAG index")
    args = parser.parse_args()

    cfg = load()
    if args.cmd == "build":
        result = build(cfg)
        print(f"Indexed {result.documents} documents at {result.index_path}")


if __name__ == "__main__":
    main()
