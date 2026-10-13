"""Mock ride / airport pickup provider."""
from __future__ import annotations

from typing import Any


def propose_reschedule(booking: dict[str, Any], new_pickup: str) -> dict[str, Any]:
    return {
        "booking_id": booking["id"],
        "action": "reschedule_pickup",
        "original_pickup": booking["details"]["pickup_time"],
        "proposed_pickup": new_pickup,
        "status": "proposed",
        "cost_delta": 0,
        "message": "Reschedule airport pickup to new arrival time.",
    }


def apply_reschedule(booking_id: str, new_pickup: str) -> dict[str, Any]:
    return {
        "booking_id": booking_id,
        "status": "success",
        "new_pickup": new_pickup,
        "message": "Pickup rescheduled successfully.",
    }


def compensate_reschedule(booking_id: str, original_pickup: str) -> dict[str, Any]:
    return {
        "booking_id": booking_id,
        "status": "compensated",
        "restored_pickup": original_pickup,
        "message": "Pickup time restored to original.",
    }
