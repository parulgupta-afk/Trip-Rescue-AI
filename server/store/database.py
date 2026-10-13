"""SQLite database helpers."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Iterator

# Allow override; default /tmp for sandboxes with restricted disk, else project-local
_DEFAULT = Path(os.environ.get("TRIP_RESCUE_DB", "/tmp/trip_rescue.db"))
DB_PATH = _DEFAULT
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def db_session() -> Iterator[sqlite3.Connection]:
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create tables if they do not exist."""
    with db_session() as conn:
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        conn.executescript(schema)
