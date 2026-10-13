"""MCP tools – Tier A read operations + plan proposal."""
from __future__ import annotations

from typing import Any

from server.providers import flight_provider
from server.store import repositories as repo
from server.domain.plan_engine import propose_rescue_plan as engine_propose
from server.store.database import init_db


# Ensure DB + seed on import for demo
init_db()
repo.seed_demo_data()


def get_trip(trip_id: str = "TRIP-100") -> dict[str, Any]:
    """Retrieve the full itinerary (segments + bookings)."""
    trip = repo.get_trip(trip_id)
    if not trip:
        return {"error": f"Trip {trip_id} not found"}
    return trip


def check_flight_status(trip_id: str = "TRIP-100") -> dict[str, Any]:
    """Detect disruption and list affected itinerary items."""
    trip = repo.get_trip(trip_id)
    if not trip:
        return {"error": f"Trip {trip_id} not found"}
    return flight_provider.check_flight_status(trip)


def get_preferences(user_id: str = "user-alex") -> dict[str, Any]:
    """Return saved travel preferences."""
    return repo.get_preferences(user_id)


def search_alternatives(
    trip_id: str = "TRIP-100",
    user_id: str = "user-alex",
) -> dict[str, Any]:
    """Search and rank alternative flights against preferences."""
    trip = repo.get_trip(trip_id)
    if not trip:
        return {"error": f"Trip {trip_id} not found"}
    prefs = repo.get_preferences(user_id)
    ranked = flight_provider.search_alternatives(trip, prefs)
    return {"alternatives": ranked, "count": len(ranked)}


def propose_rescue_plan(
    selected_flight_id: str,
    trip_id: str = "TRIP-100",
    user_id: str = "user-alex",
) -> dict[str, Any]:
    """
    Generate a coordinated recovery plan for the selected flight.
    Does NOT execute anything – returns a plan awaiting approval.
    """
    try:
        plan = engine_propose(trip_id, user_id, selected_flight_id)
        return plan
    except ValueError as e:
        return {"error": str(e)}


def save_preference(
    key: str,
    value: Any,
    user_id: str = "user-alex",
    source: str = "explicit",
) -> dict[str, Any]:
    """Persist a user preference."""
    repo.save_preference(user_id, key, value, source)
    return {"status": "saved", "key": key, "value": value}
