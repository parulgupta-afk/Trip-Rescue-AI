"""Mock messaging provider (notifications)."""
from __future__ import annotations

import threading
from typing import Any, Callable

# Test hooks — production path leaves these as no-ops
_send_count = 0
_send_lock = threading.Lock()
_before_send: Callable[[], None] | None = None


def reset_send_hooks() -> None:
    global _send_count, _before_send
    with _send_lock:
        _send_count = 0
        _before_send = None


def get_send_count() -> int:
    with _send_lock:
        return _send_count


def set_before_send(fn: Callable[[], None] | None) -> None:
    global _before_send
    _before_send = fn


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
    """Simulate send – irreversible. Only one concurrent claim should reach here."""
    global _send_count
    hook = _before_send
    if hook is not None:
        hook()
    with _send_lock:
        _send_count += 1
    return {
        **draft,
        "status": "sent",
        "message": "Notification delivered (mock).",
    }
