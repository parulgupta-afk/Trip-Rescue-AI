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


# ---------- Phase 4: Approval + Execution ----------

from server.domain import approval_service, execution_service


def approve_rescue_plan(
    plan_id: str,
    plan_hash: str,
    user_id: str = "user-alex",
) -> dict:
    """Record explicit approval of the exact plan (hash-bound)."""
    return approval_service.approve_plan(plan_id, plan_hash, user_id)


def execute_rescue_plan(
    plan_id: str,
    user_id: str = "user-alex",
    force_fail_step: str | None = None,
) -> dict:
    """
    Execute an approved plan.
    Optionally force a failure on a named step for demo (e.g. 'reschedule_ride').
    """
    if force_fail_step:
        execution_service.set_force_fail(force_fail_step)
    else:
        execution_service.set_force_fail(None)
    return execution_service.execute_plan(plan_id, user_id)


def get_plan_status(plan_id: str) -> dict:
    """Return plan status and execution step results."""
    return execution_service.get_plan_status(plan_id)


# ---------- Phase 5: Notifications ----------

from server.domain import notification_service


def draft_notifications(plan_id: str, user_id: str = "user-alex") -> dict:
    """Draft notification messages for review. Does not send."""
    return notification_service.draft_notifications(plan_id, user_id)


def send_notifications(
    plan_id: str,
    approved: bool = False,
    user_id: str = "user-alex",
) -> dict:
    """Send reviewed notifications. Requires approved=True."""
    return notification_service.send_notifications(plan_id, approved, user_id)


def list_preferences(user_id: str = "user-alex") -> dict:
    """List all saved preferences for the user (memory demo)."""
    prefs = get_preferences(user_id)
    return {"user_id": user_id, "preferences": prefs, "count": len(prefs)}
