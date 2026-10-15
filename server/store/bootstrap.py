"""Schema init and optional demo seed — never auto-wipe production data."""
from __future__ import annotations

from server.store.database import init_db
from server.store import repositories as repo


def ensure_schema() -> None:
    """Create tables if missing. Does not delete data."""
    init_db()
    migrate_schema()


def ensure_demo_fixtures(*, force: bool = False) -> dict:
    """
    Ensure demo user/trip exist for the hackathon simulator.
    By default only inserts if the demo trip is missing.
    force=True wipes and reseeds (tests / explicit CLI only).
    """
    ensure_schema()
    if force:
        repo.seed_demo_data(wipe=True)
        return {"seeded": True, "mode": "wipe"}
    existing = repo.get_trip("TRIP-100")
    if existing:
        return {"seeded": False, "mode": "already_present"}
    repo.seed_demo_data(wipe=False)
    return {"seeded": True, "mode": "insert_missing"}


def migrate_schema() -> None:
    """Non-destructive column adds for existing SQLite DBs."""
    from server.store.database import db_session
    with db_session() as conn:
        try:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(notification_sends)").fetchall()}
        except Exception:
            return
        if "claimed_at" not in cols:
            conn.execute("ALTER TABLE notification_sends ADD COLUMN claimed_at TEXT")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS execution_claims (
                plan_id TEXT PRIMARY KEY,
                claimed_at TEXT NOT NULL,
                worker_id TEXT
            )"""
        )
