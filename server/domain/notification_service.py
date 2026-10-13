"""Notification drafting + send (requires separate approval)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from server.store.database import db_session
from server.providers import message_provider


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id() -> str:
    return str(uuid.uuid4())


def draft_notifications(plan_id: str, user_id: str = "user-alex") -> dict[str, Any]:
    """Build notification drafts from plan actions. Does not send."""
    with db_session() as conn:
        plan = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
        if not plan:
            return {"error": f"Plan {plan_id} not found"}
        actions = json.loads(plan["actions_json"])

    drafts = []
    for a in actions:
        if a.get("type") == "draft_notification":
            drafts.append({
                "id": _id(),
                "recipient": a.get("recipient", "Sam"),
                "subject": "Updated arrival time",
                "body": a.get("body", ""),
                "status": "draft",
            })

    if not drafts:
        # Fallback draft
        drafts.append(message_provider.draft_arrival_message("Sam", "updated time"))

    return {
        "plan_id": plan_id,
        "drafts": drafts,
        "status": "awaiting_send_approval",
        "message": "Review drafts before sending. Send requires explicit approval.",
    }


def send_notifications(
    plan_id: str,
    approved: bool = False,
    user_id: str = "user-alex",
) -> dict[str, Any]:
    """Send reviewed notifications only when approved=True."""
    if not approved:
        return {
            "ok": False,
            "error": "NOT_APPROVED",
            "message": "Notifications require explicit send approval (approved=true).",
        }

    draft_result = draft_notifications(plan_id, user_id)
    if "error" in draft_result:
        return draft_result

    sent = []
    for d in draft_result["drafts"]:
        result = message_provider.send_message(d)
        sent.append(result)

    return {
        "ok": True,
        "plan_id": plan_id,
        "sent": sent,
        "message": f"Sent {len(sent)} notification(s) via mock provider.",
    }
