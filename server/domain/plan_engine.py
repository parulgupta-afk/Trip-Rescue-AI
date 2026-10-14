"""Rescue plan engine – pure proposal generation + hashing."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from server.providers import flight_provider, hotel_provider, ride_provider, message_provider
from server.store import repositories as repo


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def compute_plan_hash(actions: list[dict], total_cost_delta: int, trip_id: str) -> str:
    payload = {
        "trip_id": trip_id,
        "actions": actions,
        "total_cost_delta": total_cost_delta,
    }
    return hashlib.sha256(_canonical_json(payload).encode()).hexdigest()


def propose_rescue_plan(
    trip_id: str,
    user_id: str,
    selected_flight_id: str,
    allow_budget_override: bool = False,
) -> dict[str, Any]:
    """
    Build a complete recovery plan for the selected alternative flight.
    No side-effects – only persists the proposal.
    Rejects plans exceeding user's max_additional_cost unless allow_budget_override=True.
    """
    trip = repo.get_trip(trip_id)
    if not trip:
        raise ValueError(f"Trip {trip_id} not found")

    preferences = repo.get_preferences(user_id)
    alternatives = flight_provider.search_alternatives(trip, preferences)
    selected = next((a for a in alternatives if a["id"] == selected_flight_id), None)
    if not selected:
        raise ValueError(f"Flight {selected_flight_id} not found in alternatives")

    hotel = next((b for b in trip["bookings"] if b["kind"] == "hotel"), None)
    ride = next((b for b in trip["bookings"] if b["kind"] == "ride"), None)

    actions: list[dict] = []

    # Flight change
    actions.append({
        "type": "change_flight",
        "target": selected["id"],
        "flight_number": selected["flight_number"],
        "airline": selected["airline"],
        "departure": selected["departure"],
        "arrival": selected["arrival"],
        "cost_delta": selected["extra_cost"],
        "reason": selected["why"],
    })

    # Hotel
    if hotel:
        hotel_prop = hotel_provider.propose_later_checkin(hotel, selected["arrival"])
        actions.append({
            "type": "reschedule_hotel",
            "target": hotel["id"],
            "original_check_in": hotel_prop["original_check_in"],
            "proposed_check_in": hotel_prop["proposed_check_in"],
            "cost_delta": 0,
        })

    # Ride
    if ride:
        ride_prop = ride_provider.propose_reschedule(ride, selected["arrival"])
        actions.append({
            "type": "reschedule_ride",
            "target": ride["id"],
            "original_pickup": ride_prop["original_pickup"],
            "proposed_pickup": ride_prop["proposed_pickup"],
            "cost_delta": 0,
        })

    # Notification draft (still proposal)
    notif = message_provider.draft_arrival_message(
        recipient="Sam",
        new_arrival=selected["arrival"],
        traveller_name="Alex",
    )
    actions.append({
        "type": "draft_notification",
        "recipient": notif["recipient"],
        "body": notif["body"],
        "cost_delta": 0,
    })

    total_cost = sum(a.get("cost_delta", 0) for a in actions)

    max_cost = preferences.get("max_additional_cost", {}).get("value", 3000)
    try:
        max_cost = int(max_cost)
    except (TypeError, ValueError):
        max_cost = 3000
    if total_cost > max_cost:
        if not allow_budget_override:
            raise ValueError(
                f"Plan cost +{total_cost} exceeds max additional cost {max_cost}. "
                "Choose a lower-cost alternative, raise your budget preference, or explicitly set allow_budget_override=True."
            )

    plan_hash = compute_plan_hash(actions, total_cost, trip_id)

    plan = repo.create_plan(
        trip_id=trip_id,
        user_id=user_id,
        actions=actions,
        total_cost_delta=total_cost,
        plan_hash=plan_hash,
    )
    plan["selected_flight"] = selected
    plan["status"] = "awaiting_approval"
    return plan
