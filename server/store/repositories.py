"""Repository layer – thin wrappers over SQLite."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from server.store.database import db_session


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id() -> str:
    return str(uuid.uuid4())


# ---------- Seed / Fixtures ----------

def seed_demo_data(*, wipe: bool = False) -> None:
    """Insert deterministic demo traveller, trip, segments, bookings, preferences.

    wipe=True deletes existing rows (tests only). wipe=False only inserts
    if the demo user is missing — never clears plans/preferences/history.
    """
    with db_session() as conn:
        if wipe:
            conn.execute("PRAGMA foreign_keys = OFF")
            for table in (
                "notification_sends", "notification_approvals", "notification_drafts",
                "audit_log", "execution_steps", "approvals", "plans",
                "preferences", "bookings", "segments", "trips", "users"
            ):
                conn.execute(f"DELETE FROM {table}")
            conn.execute("PRAGMA foreign_keys = ON")

        user_id = "user-alex"
        trip_id = "TRIP-100"
        existing = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if existing and not wipe:
            return

        conn.execute(
            "INSERT INTO users (id, name, timezone, created_at) VALUES (?, ?, ?, ?)",
            (user_id, "Alex", "Asia/Kolkata", _now()),
        )
        conn.execute(
            "INSERT INTO trips (id, user_id, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (trip_id, user_id, "active", _now(), _now()),
        )

        # Segment 1 – delayed
        conn.execute(
            """INSERT INTO segments
               (id, trip_id, flight_number, origin, destination, departure_time, arrival_time, status, airline, seat)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "SEG-1", trip_id, "EX-401", "DEL", "LHR",
                "2026-10-20T18:00:00+05:30", "2026-10-20T23:30:00+01:00",
                "delayed", "Example Air", "12A",
            ),
        )
        # Segment 2 – connection at risk
        conn.execute(
            """INSERT INTO segments
               (id, trip_id, flight_number, origin, destination, departure_time, arrival_time, status, airline, seat)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "SEG-2", trip_id, "EX-902", "LHR", "JFK",
                "2026-10-21T01:00:00+01:00", "2026-10-21T04:30:00-04:00",
                "scheduled", "Example Air", "14C",
            ),
        )

        # Hotel
        conn.execute(
            """INSERT INTO bookings (id, trip_id, kind, provider_reference, details_json, status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                "HOTEL-100", trip_id, "hotel", "HTL-7788",
                json.dumps({
                    "name": "Manhattan View Hotel",
                    "check_in": "2026-10-21T15:00:00-04:00",
                    "check_out": "2026-10-24T11:00:00-04:00",
                    "address": "New York, NY",
                }),
                "confirmed",
            ),
        )
        # Ride
        conn.execute(
            """INSERT INTO bookings (id, trip_id, kind, provider_reference, details_json, status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                "RIDE-100", trip_id, "ride", "RIDE-4455",
                json.dumps({
                    "pickup_time": "2026-10-21T05:00:00-04:00",
                    "location": "JFK Terminal 4",
                    "driver": "Sam",
                }),
                "confirmed",
            ),
        )

        # Preferences
        prefs = {
            "preferred_airline": "Example Air",
            "seat": "aisle",
            "avoid_overnight": True,
            "max_additional_cost": 3000,
        }
        for key, value in prefs.items():
            conn.execute(
                """INSERT INTO preferences (id, user_id, key, value_json, source, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (_id(), user_id, key, json.dumps(value), "explicit", _now()),
            )


# ---------- Read helpers ----------

def get_user(user_id: str) -> dict[str, Any] | None:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def get_trip(trip_id: str) -> dict[str, Any] | None:
    with db_session() as conn:
        trip = conn.execute("SELECT * FROM trips WHERE id = ?", (trip_id,)).fetchone()
        if not trip:
            return None
        segments = conn.execute(
            "SELECT * FROM segments WHERE trip_id = ? ORDER BY departure_time", (trip_id,)
        ).fetchall()
        bookings = conn.execute(
            "SELECT * FROM bookings WHERE trip_id = ?", (trip_id,)
        ).fetchall()
        return {
            **dict(trip),
            "segments": [dict(s) for s in segments],
            "bookings": [
                {**dict(b), "details": json.loads(b["details_json"])}
                for b in bookings
            ],
        }


def get_preferences(user_id: str) -> dict[str, Any]:
    with db_session() as conn:
        rows = conn.execute(
            "SELECT key, value_json, source FROM preferences WHERE user_id = ?", (user_id,)
        ).fetchall()
        return {
            r["key"]: {"value": json.loads(r["value_json"]), "source": r["source"]}
            for r in rows
        }


def save_preference(user_id: str, key: str, value: Any, source: str = "explicit") -> None:
    with db_session() as conn:
        existing = conn.execute(
            "SELECT id FROM preferences WHERE user_id = ? AND key = ?", (user_id, key)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE preferences SET value_json = ?, source = ?, updated_at = ? WHERE id = ?",
                (json.dumps(value), source, _now(), existing["id"]),
            )
        else:
            conn.execute(
                """INSERT INTO preferences (id, user_id, key, value_json, source, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (_id(), user_id, key, json.dumps(value), source, _now()),
            )


def create_plan(
    trip_id: str,
    user_id: str,
    actions: list[dict],
    total_cost_delta: int,
    plan_hash: str,
    expires_at: str | None = None,
) -> dict[str, Any]:
    plan_id = f"TR-{uuid.uuid4().hex[:6].upper()}"
    with db_session() as conn:
        # version = max existing + 1 for this trip
        row = conn.execute(
            "SELECT COALESCE(MAX(version), 0) AS v FROM plans WHERE trip_id = ?", (trip_id,)
        ).fetchone()
        version = row["v"] + 1
        conn.execute(
            """INSERT INTO plans
               (id, trip_id, user_id, version, actions_json, total_cost_delta, plan_hash, status, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                plan_id, trip_id, user_id, version, json.dumps(actions),
                total_cost_delta, plan_hash, "pending", _now(), expires_at,
            ),
        )
    return {
        "plan_id": plan_id,
        "version": version,
        "trip_id": trip_id,
        "user_id": user_id,
        "actions": actions,
        "total_cost_delta": total_cost_delta,
        "plan_hash": plan_hash,
        "status": "pending",
    }


def get_plan(plan_id: str) -> dict[str, Any] | None:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["actions"] = json.loads(d["actions_json"])
        return d


def delete_preference(user_id: str, key: str) -> None:
    with db_session() as conn:
        conn.execute(
            "DELETE FROM preferences WHERE user_id = ? AND key = ?",
            (user_id, key),
        )
