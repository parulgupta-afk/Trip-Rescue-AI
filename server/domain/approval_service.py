"""Approval service – hash-bound, expiring, ownership-checked approvals."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from server.store.database import db_session
from server.store import repositories as repo


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def approve_plan(
    plan_id: str,
    submitted_hash: str,
    user_id: str = "user-alex",
    expiry_minutes: int = 30,
) -> dict[str, Any]:
    """
    Record explicit approval of an exact plan version.
    Rejects if hash mismatch, wrong owner, already consumed, expired, or not pending.
    """
    plan = repo.get_plan(plan_id)
    if not plan:
        return {"ok": False, "error": "PLAN_NOT_FOUND", "message": f"Plan {plan_id} not found"}

    if plan["user_id"] != user_id:
        return {"ok": False, "error": "OWNERSHIP", "message": "Plan does not belong to this user"}

    if plan["status"] != "pending":
        return {
            "ok": False,
            "error": "INVALID_STATUS",
            "message": f"Plan status is '{plan['status']}', expected 'pending'",
        }

    if plan["plan_hash"] != submitted_hash:
        return {
            "ok": False,
            "error": "HASH_MISMATCH",
            "message": "Submitted plan hash does not match the current plan. Approve the exact displayed plan.",
        }

    # Check existing unconsumed approval
    with db_session() as conn:
        existing = conn.execute(
            "SELECT * FROM approvals WHERE plan_id = ? AND consumed_at IS NULL",
            (plan_id,),
        ).fetchone()
        if existing:
            return {
                "ok": False,
                "error": "ALREADY_APPROVED",
                "message": "Plan already has an active approval",
                "approval_id": existing["id"],
            }

        approval_id = str(uuid.uuid4())
        expires_at = (_now() + timedelta(minutes=expiry_minutes)).isoformat()
        conn.execute(
            """INSERT INTO approvals
               (id, plan_id, plan_hash, approved_by, approved_at, expires_at, consumed_at)
               VALUES (?, ?, ?, ?, ?, ?, NULL)""",
            (approval_id, plan_id, submitted_hash, user_id, _now_iso(), expires_at),
        )
        conn.execute(
            "UPDATE plans SET status = 'approved' WHERE id = ?",
            (plan_id,),
        )

    return {
        "ok": True,
        "approval_id": approval_id,
        "plan_id": plan_id,
        "plan_hash": submitted_hash,
        "approved_at": _now_iso(),
        "expires_at": expires_at,
        "message": "Plan approved. Ready for execution.",
    }


def get_valid_approval(plan_id: str, user_id: str) -> dict[str, Any] | None:
    """Return the active, unexpired, unconsumed approval or None."""
    with db_session() as conn:
        row = conn.execute(
            """SELECT * FROM approvals
               WHERE plan_id = ? AND approved_by = ? AND consumed_at IS NULL
               ORDER BY approved_at DESC LIMIT 1""",
            (plan_id, user_id),
        ).fetchone()
        if not row:
            return None
        approval = dict(row)
        if approval.get("expires_at"):
            exp = datetime.fromisoformat(approval["expires_at"])
            if _now() > exp:
                return None
        return approval


def consume_approval(approval_id: str) -> None:
    with db_session() as conn:
        conn.execute(
            "UPDATE approvals SET consumed_at = ? WHERE id = ?",
            (_now_iso(), approval_id),
        )
