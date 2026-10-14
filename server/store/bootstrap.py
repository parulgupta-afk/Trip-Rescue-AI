"""Schema init and optional demo seed — never auto-wipe production data."""
from __future__ import annotations

from server.store.database import init_db
from server.store import repositories as repo


def ensure_schema() -> None:
    """Create tables if missing. Does not delete data."""
    init_db()


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
