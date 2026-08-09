from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path


def _value(database: Path) -> str:
    with sqlite3.connect(database) as connection:
        row = connection.execute("SELECT value FROM sample LIMIT 1").fetchone()
    assert row is not None
    return str(row[0])


def test_sqlite_backup_and_restore_round_trip(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    backup = tmp_path / "backups" / "snapshot.db"
    restored = tmp_path / "restored.db"

    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE sample (value TEXT NOT NULL)")
        connection.execute("INSERT INTO sample(value) VALUES (?)", ("persistent evidence",))
        connection.commit()

    subprocess.run(
        [
            sys.executable,
            "scripts/sqlite_backup.py",
            "backup",
            "--source",
            str(source),
            "--output",
            str(backup),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert backup.is_file()
    assert _value(backup) == "persistent evidence"

    restored.write_bytes(b"stale destination")
    stale_wal = Path(f"{restored}-wal")
    stale_shm = Path(f"{restored}-shm")
    stale_wal.write_bytes(b"stale wal")
    stale_shm.write_bytes(b"stale shm")

    subprocess.run(
        [
            sys.executable,
            "scripts/sqlite_backup.py",
            "restore",
            "--source",
            str(backup),
            "--output",
            str(restored),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert _value(restored) == "persistent evidence"
    assert not stale_wal.exists()
    assert not stale_shm.exists()
