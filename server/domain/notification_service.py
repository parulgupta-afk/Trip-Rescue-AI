"""Notification drafting + hash-bound send approval."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from server.store.database import db_session
from server.store import repositories as repo
from server.providers import message_provider


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _id() -> str:
    return str(uuid.uuid4())


def _content_hash(drafts: list[dict]) -> str:
    canonical = json.dumps(drafts, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def draft_notifications(plan_id: str, user_id: str = "user-alex") -> dict[str, Any]:
    """Build and persist notification drafts from plan actions."""
    plan = repo.get_plan(plan_id)
    if not plan:
        return {"ok": False, "error": "PLAN_NOT_FOUND", "message": f"Plan {plan_id} not found"}
    if plan["user_id"] != user_id:
        return {"ok": False, "error": "OWNERSHIP", "message": "Plan does not belong to this user"}

    actions = plan["actions"]
    drafts = []
    for a in actions:
        if a.get("type") == "draft_notification":
            drafts.append({
                "recipient": a.get("recipient", "Sam"),
                "subject": "Updated arrival time",
                "body": a.get("body", ""),
            })
    if not drafts:
        d = message_provider.draft_arrival_message("Sam", "updated time")
        drafts.append({
            "recipient": d["recipient"],
            "subject": d.get("subject", "Updated arrival time"),
            "body": d["body"],
        })

    content_hash = _content_hash(drafts)
    draft_id = f"ND-{uuid.uuid4().hex[:8].upper()}"

    with db_session() as conn:
        conn.execute(
            """INSERT INTO notification_drafts
               (id, plan_id, user_id, drafts_json, content_hash, status, created_at)
               VALUES (?, ?, ?, ?, ?, 'draft', ?)""",
            (draft_id, plan_id, user_id, json.dumps(drafts), content_hash, _now_iso()),
        )

    return {
        "ok": True,
        "plan_id": plan_id,
        "draft_id": draft_id,
        "drafts": drafts,
        "content_hash": content_hash,
        "status": "awaiting_send_approval",
        "message": "Review drafts before approving send. Hash-bound approval required.",
        "provider": "simulated",
    }


def approve_notifications(
    plan_id: str,
    draft_hash: str,
    user_id: str = "user-alex",
    expiry_minutes: int = 30,
) -> dict[str, Any]:
    """Approve exact notification draft content."""
    plan = repo.get_plan(plan_id)
    if not plan:
        return {"ok": False, "error": "PLAN_NOT_FOUND", "message": f"Plan {plan_id} not found"}
    if plan["user_id"] != user_id:
        return {"ok": False, "error": "OWNERSHIP", "message": "Plan does not belong to this user"}

    if plan["status"] not in ("approved", "executing", "succeeded"):
        return {
            "ok": False,
            "error": "INVALID_PLAN_STATUS",
            "message": f"Cannot approve notifications for plan with status '{plan['status']}'. Plan must be approved or executed first.",
        }

    with db_session() as conn:
        row = conn.execute(
            """SELECT * FROM notification_drafts
               WHERE plan_id = ? AND user_id = ?
               ORDER BY created_at DESC LIMIT 1""",
            (plan_id, user_id),
        ).fetchone()
        if not row:
            return {"ok": False, "error": "NO_DRAFT", "message": "No notification draft found"}
        draft = dict(row)
        if draft["status"] == "sent":
            return {"ok": False, "error": "ALREADY_SENT", "message": "Notification draft has already been sent."}
        if draft["content_hash"] != draft_hash:
            return {
                "ok": False,
                "error": "HASH_MISMATCH",
                "message": "Draft content hash does not match. Re-draft and re-approve.",
            }
        approval_id = _id()
        expires_at = (_now() + timedelta(minutes=expiry_minutes)).isoformat()
        conn.execute(
            """INSERT INTO notification_approvals
               (id, plan_id, draft_id, content_hash, approved_by, approved_at, expires_at, consumed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, NULL)""",
            (approval_id, plan_id, draft["id"], draft_hash, user_id, _now_iso(), expires_at),
        )
        conn.execute(
            "UPDATE notification_drafts SET status = 'approved' WHERE id = ?",
            (draft["id"],),
        )

    return {
        "ok": True,
        "approval_id": approval_id,
        "plan_id": plan_id,
        "draft_id": draft["id"],
        "content_hash": draft_hash,
        "expires_at": expires_at,
        "message": "Notification draft approved. Ready to send.",
    }


def send_notifications(
    plan_id: str,
    draft_hash: str | None = None,
    user_id: str = "user-alex",
) -> dict[str, Any]:
    """Send only with valid unexpired unconsumed hash-bound approval."""
    plan = repo.get_plan(plan_id)
    if not plan:
        return {"ok": False, "error": "PLAN_NOT_FOUND", "message": f"Plan {plan_id} not found"}
    if plan["user_id"] != user_id:
        return {"ok": False, "error": "OWNERSHIP", "message": "Plan does not belong to this user"}

    if not draft_hash or not str(draft_hash).strip():
        return {
            "ok": False,
            "error": "HASH_REQUIRED",
            "message": "Notification send requires the exact draft content hash that was approved.",
        }

    if plan["status"] not in ("approved", "executing", "succeeded"):
        return {
            "ok": False,
            "error": "INVALID_PLAN_STATUS",
            "message": f"Cannot send notifications for plan with status '{plan['status']}'. Plan must be approved or executed first.",
        }

    with db_session() as conn:
        draft_row = conn.execute(
            """SELECT * FROM notification_drafts
               WHERE plan_id = ? AND user_id = ?
               ORDER BY created_at DESC LIMIT 1""",
            (plan_id, user_id),
        ).fetchone()
        if not draft_row:
            return {"ok": False, "error": "NO_DRAFT", "message": "No notification draft found"}
        draft = dict(draft_row)

        if draft["content_hash"] != draft_hash:
            return {
                "ok": False,
                "error": "HASH_MISMATCH",
                "message": "Submitted draft hash does not match stored draft.",
            }
        content_hash = draft_hash

        # Idempotency: already sent this content
        existing_send = conn.execute(
            "SELECT * FROM notification_sends WHERE plan_id = ? AND content_hash = ?",
            (plan_id, content_hash),
        ).fetchone()
        if existing_send:
            es = dict(existing_send)
            return {
                "ok": True,
                "idempotent": True,
                "plan_id": plan_id,
                "status": es["status"],
                "sent": json.loads(es["result_json"]),
                "message": "Notifications already sent for this draft (idempotent).",
                "provider": "simulated",
            }

        approval = conn.execute(
            """SELECT * FROM notification_approvals
               WHERE plan_id = ? AND content_hash = ? AND approved_by = ?
                 AND consumed_at IS NULL
               ORDER BY approved_at DESC LIMIT 1""",
            (plan_id, content_hash, user_id),
        ).fetchone()
        if not approval:
            return {
                "ok": False,
                "error": "NOT_APPROVED",
                "message": "No valid notification approval for this draft hash.",
            }
        approval = dict(approval)
        if approval.get("expires_at"):
            exp = datetime.fromisoformat(approval["expires_at"])
            if _now() > exp:
                return {
                    "ok": False,
                    "error": "EXPIRED",
                    "message": "Notification approval has expired.",
                }

        drafts = json.loads(draft["drafts_json"])
        sent = []
        for d in drafts:
            result = message_provider.send_message({**d, "status": "draft"})
            sent.append(result)

        send_id = _id()
        conn.execute(
            """INSERT INTO notification_sends
               (id, plan_id, draft_id, content_hash, result_json, status, created_at)
               VALUES (?, ?, ?, ?, ?, 'sent', ?)""",
            (send_id, plan_id, draft["id"], content_hash, json.dumps(sent), _now_iso()),
        )
        conn.execute(
            "UPDATE notification_approvals SET consumed_at = ? WHERE id = ?",
            (_now_iso(), approval["id"]),
        )
        conn.execute(
            "UPDATE notification_drafts SET status = 'sent' WHERE id = ?",
            (draft["id"],),
        )

    return {
        "ok": True,
        "plan_id": plan_id,
        "draft_id": draft["id"],
        "sent": sent,
        "status": "sent",
        "message": f"Sent {len(sent)} notification(s) via simulated mock provider.",
        "provider": "simulated",
    }
