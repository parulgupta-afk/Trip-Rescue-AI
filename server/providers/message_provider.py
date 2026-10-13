"""Mock messaging provider (notifications)."""
from __future__ import annotations

from typing import Any


def draft_arrival_message(
    recipient: str,
    new_arrival: str,
    traveller_name: str = "Alex",
) -> dict[str, Any]:
    body = (
        f"Hi {recipient}, my flight was delayed, but I've arranged an alternative. "
        f"My updated arrival time is {new_arrival}. I'll share any further changes."
    )
    return {
        "recipient": recipient,
        "subject": "Updated arrival time",
        "body": body,
        "status": "draft",
    }


def send_message(draft: dict[str, Any]) -> dict[str, Any]:
    """Simulate send – irreversible."""
    return {
        **draft,
        "status": "sent",
        "message": "Notification delivered (mock).",
    }
