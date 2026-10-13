"""Mock hotel provider."""
from __future__ import annotations

from typing import Any


def propose_later_checkin(booking: dict[str, Any], new_arrival: str) -> dict[str, Any]:
    return {
        "booking_id": booking["id"],
        "action": "request_later_checkin",
        "original_check_in": booking["details"]["check_in"],
        "proposed_check_in": new_arrival,
        "status": "proposed",
        "cost_delta": 0,
        "message": "Request later check-in to match new arrival time.",
    }


def apply_checkin_change(booking_id: str, new_check_in: str) -> dict[str, Any]:
    """Simulate successful hotel update."""
    return {
        "booking_id": booking_id,
        "status": "success",
        "new_check_in": new_check_in,
        "message": "Hotel check-in updated successfully.",
    }


def compensate_checkin(booking_id: str, original_check_in: str) -> dict[str, Any]:
    return {
        "booking_id": booking_id,
        "status": "compensated",
        "restored_check_in": original_check_in,
        "message": "Hotel check-in restored to original.",
    }
