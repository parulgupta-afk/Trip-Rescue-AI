"""MCP tools – read / propose / commit operations.

Schema is ensured on first use. Demo data is NOT wiped on import.
"""
from __future__ import annotations

from typing import Any

from server.providers import flight_provider
from server.store import repositories as repo
from server.domain.plan_engine import propose_rescue_plan as engine_propose
from server.store.bootstrap import ensure_schema, ensure_demo_fixtures

_initialized = False


def _ensure_ready() -> None:
    global _initialized
    if _initialized:
        return
    ensure_schema()
    ensure_demo_fixtures(force=False)
    _initialized = True


def get_trip(trip_id: str = "TRIP-100") -> dict[str, Any]:
    """Retrieve the full itinerary (segments + bookings)."""
    _ensure_ready()
    trip = repo.get_trip(trip_id)
    if not trip:
        return {"error": f"Trip {trip_id} not found"}
    return trip


def check_flight_status(trip_id: str = "TRIP-100") -> dict[str, Any]:
    """Detect disruption and list affected itinerary items."""
    _ensure_ready()
    trip = repo.get_trip(trip_id)
    if not trip:
        return {"error": f"Trip {trip_id} not found"}
    return flight_provider.check_flight_status(trip)


def get_preferences(user_id: str = "user-alex") -> dict[str, Any]:
    """Return saved travel preferences."""
    _ensure_ready()
    return repo.get_preferences(user_id)


def search_alternatives(
    trip_id: str = "TRIP-100",
    user_id: str = "user-alex",
) -> dict[str, Any]:
    """Search and rank alternative flights against preferences."""
    _ensure_ready()
    trip = repo.get_trip(trip_id)
    if not trip:
        return {"error": f"Trip {trip_id} not found"}
    prefs = repo.get_preferences(user_id)
    ranked = flight_provider.search_alternatives(trip, prefs)
    return {"alternatives": ranked, "count": len(ranked), "provider": "simulated"}


def propose_rescue_plan(
    selected_flight_id: str,
    trip_id: str = "TRIP-100",
    user_id: str = "user-alex",
    allow_budget_override: bool = False,
) -> dict[str, Any]:
    """
    Generate a coordinated recovery plan for the selected flight.
    Does NOT execute anything – returns a plan awaiting approval.
    Rejects over-budget selections unless within max_additional_cost or allow_budget_override=True.
    """
    _ensure_ready()
    try:
        plan = engine_propose(trip_id, user_id, selected_flight_id, allow_budget_override=allow_budget_override)
        return plan
    except ValueError as e:
        return {"error": str(e), "ok": False}


def save_preference(
    key: str,
    value: Any,
    user_id: str = "user-alex",
    source: str = "explicit",
) -> dict[str, Any]:
    """Persist a user preference."""
    _ensure_ready()
    repo.save_preference(user_id, key, value, source)
    return {"status": "saved", "key": key, "value": value}


def delete_preference(key: str, user_id: str = "user-alex") -> dict[str, Any]:
    """Delete a saved preference."""
    _ensure_ready()
    repo.delete_preference(user_id, key)
    return {"status": "deleted", "key": key}


from server.domain import approval_service, execution_service, notification_service


def approve_rescue_plan(
    plan_id: str,
    plan_hash: str,
    user_id: str = "user-alex",
) -> dict:
    """Record explicit approval of the exact plan (hash-bound)."""
    _ensure_ready()
    return approval_service.approve_plan(plan_id, plan_hash, user_id)


def execute_rescue_plan(
    plan_id: str,
    user_id: str = "user-alex",
    force_fail_step: str | None = None,
) -> dict:
    """Execute an approved plan. Optional force_fail_step for compensation demo."""
    _ensure_ready()
    if force_fail_step:
        execution_service.set_force_fail(force_fail_step)
    else:
        execution_service.set_force_fail(None)
    return execution_service.execute_plan(plan_id, user_id)


def get_plan_status(plan_id: str, user_id: str = "user-alex") -> dict:
    """Return plan status and execution step results (ownership enforced)."""
    _ensure_ready()
    return execution_service.get_plan_status(plan_id, user_id)


def draft_notifications(plan_id: str, user_id: str = "user-alex") -> dict:
    """Draft notification messages for review. Persists drafts with content hash."""
    _ensure_ready()
    return notification_service.draft_notifications(plan_id, user_id)


def approve_notifications(
    plan_id: str,
    draft_hash: str,
    user_id: str = "user-alex",
) -> dict:
    """Approve exact notification draft content (hash-bound)."""
    _ensure_ready()
    return notification_service.approve_notifications(plan_id, draft_hash, user_id)


def send_notifications(
    plan_id: str,
    draft_hash: str | None = None,
    user_id: str = "user-alex",
    approved: bool | None = None,  # deprecated — ignored for authorization
) -> dict:
    """
    Send reviewed notifications.
    Requires a valid hash-bound notification approval — NOT a client boolean.
    """
    _ensure_ready()
    return notification_service.send_notifications(plan_id, draft_hash, user_id)


def list_preferences(user_id: str = "user-alex") -> dict:
    """List all saved preferences for memory demonstration."""
    _ensure_ready()
    prefs = get_preferences(user_id)
    return {"user_id": user_id, "preferences": prefs, "count": len(prefs)}


def recover_stuck_execution(plan_id: str, user_id: str = "user-alex") -> dict:
    """Mark an interrupted 'executing' plan as partially_failed; never invents success."""
    _ensure_ready()
    return execution_service.recover_stuck_execution(plan_id, user_id)


def reconcile_stale_notification_send(
    plan_id: str,
    content_hash: str,
    user_id: str = "user-alex",
    stale_after_seconds: int = 120,
) -> dict:
    """Mark a stale sending reservation as uncertain without redispatching."""
    _ensure_ready()
    return notification_service.reconcile_stale_notification_send(
        plan_id, content_hash, user_id, stale_after_seconds
    )
