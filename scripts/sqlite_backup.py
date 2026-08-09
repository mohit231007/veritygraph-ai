from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def _backup(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise SystemExit(f"Source database does not exist: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()
    with sqlite3.connect(source) as source_connection:
        with sqlite3.connect(destination) as destination_connection:
            source_connection.backup(destination_connection)
    print(f"SQLite backup written to {destination}")


def _restore(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise SystemExit(f"Backup database does not exist: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()
    with sqlite3.connect(source) as source_connection:
        with sqlite3.connect(destination) as destination_connection:
            source_connection.backup(destination_connection)
    print(f"SQLite database restored to {destination}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create or restore a consistent VerityGraph SQLite database copy.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    backup = subparsers.add_parser("backup", help="Back up a live SQLite database.")
    backup.add_argument("--source", type=Path, required=True)
    backup.add_argument("--output", type=Path, required=True)

    restore = subparsers.add_parser("restore", help="Restore a SQLite database from a backup.")
    restore.add_argument("--source", type=Path, required=True)
    restore.add_argument("--output", type=Path, required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "backup":
        _backup(args.source, args.output)
    else:
        _restore(args.source, args.output)


if __name__ == "__main__":
    main()
