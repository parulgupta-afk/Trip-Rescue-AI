"""Mock flight status + alternative search provider."""
from __future__ import annotations

from typing import Any


def check_flight_status(trip: dict[str, Any]) -> dict[str, Any]:
    """Return status for the first delayed segment and list of affected items."""
    delayed = [s for s in trip["segments"] if s["status"] == "delayed"]
    if not delayed:
        return {
            "disrupted": False,
            "message": "No disruption detected.",
            "affected": [],
        }

    seg = delayed[0]
    # 4-hour delay scenario
    return {
        "disrupted": True,
        "flight_number": seg["flight_number"],
        "delay_hours": 4,
        "original_departure": seg["departure_time"],
        "new_estimated_departure": "2026-10-20T22:00:00+05:30",
        "message": f"Flight {seg['flight_number']} delayed by 4 hours.",
        "affected": [
            {"type": "connection", "segment_id": "SEG-2", "risk": "at_risk", "reason": "Connection window too short"},
            {"type": "hotel", "booking_id": "HOTEL-100", "risk": "check_in_invalid", "reason": "Original check-in time no longer feasible"},
            {"type": "ride", "booking_id": "RIDE-100", "risk": "pickup_wrong_time", "reason": "Airport pickup scheduled for original arrival"},
        ],
    }


def search_alternatives(
    trip: dict[str, Any],
    preferences: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return deterministic ranked alternatives."""
    max_cost = preferences.get("max_additional_cost", {}).get("value", 3000)
    preferred_airline = preferences.get("preferred_airline", {}).get("value", "Example Air")
    avoid_overnight = preferences.get("avoid_overnight", {}).get("value", True)

    candidates = [
        {
            "id": "FLIGHT-A",
            "flight_number": "EX-510",
            "airline": "Example Air",
            "departure": "2026-10-20T19:15:00+05:30",
            "arrival": "2026-10-21T01:40:00-04:00",
            "extra_cost": 2000,
            "overnight": False,
            "seat_available": "aisle",
            "why": "Preferred airline, within budget, avoids overnight, feasible hotel check-in",
        },
        {
            "id": "FLIGHT-B",
            "flight_number": "XY-220",
            "airline": "Other Air",
            "departure": "2026-10-20T20:00:00+05:30",
            "arrival": "2026-10-21T02:10:00-04:00",
            "extra_cost": 1200,
            "overnight": False,
            "seat_available": "window",
            "why": "Lowest additional cost",
        },
        {
            "id": "FLIGHT-C",
            "flight_number": "EX-880",
            "airline": "Example Air",
            "departure": "2026-10-20T21:30:00+05:30",
            "arrival": "2026-10-21T03:45:00-04:00",
            "extra_cost": 0,
            "overnight": True,
            "seat_available": "aisle",
            "why": "No extra fare, but overnight flight",
        },
    ]

    # Simple ranking: prefer preferred airline, non-overnight, within budget
    def score(c: dict) -> tuple:
        airline_match = 0 if c["airline"] == preferred_airline else 1
        overnight_pen = 1 if (avoid_overnight and c["overnight"]) else 0
        cost_ok = 0 if c["extra_cost"] <= max_cost else 1
        return (cost_ok, overnight_pen, airline_match, c["extra_cost"])

    ranked = sorted(candidates, key=score)
    for i, c in enumerate(ranked, 1):
        c["rank"] = i
    return ranked
