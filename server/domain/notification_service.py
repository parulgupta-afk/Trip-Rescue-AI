"""Notification drafting + hash-bound send approval with atomic send claim."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from server.store.database import db_session, get_connection
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
            "message": (
                f"Cannot approve notifications for plan with status '{plan['status']}'. "
                "Plan must be approved or executed first."
            ),
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
        if draft.get("status") == "sent":
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


def _response_for_existing_send(plan_id: str, es: dict) -> dict[str, Any]:
    status = es.get("status") or "unknown"
    try:
        payload = json.loads(es.get("result_json") or "[]")
    except json.JSONDecodeError:
        payload = []

    if status == "sent":
        return {
            "ok": True,
            "idempotent": True,
            "plan_id": plan_id,
            "status": "sent",
            "sent": payload,
            "message": "Notifications already sent for this draft (idempotent).",
            "provider": "simulated",
        }
    if status == "sending":
        return {
            "ok": False,
            "error": "SEND_IN_PROGRESS",
            "plan_id": plan_id,
            "status": "sending",
            "message": (
                "A send reservation is already in progress for this draft. "
                "Provider was not invoked again. Wait or inspect status; do not assume delivery."
            ),
            "provider": "simulated",
        }
    if status == "uncertain":
        return {
            "ok": False,
            "error": "SEND_UNCERTAIN",
            "plan_id": plan_id,
            "status": "uncertain",
            "sent": payload,
            "message": (
                "A previous send attempt left an uncertain outcome. "
                "Provider was not re-dispatched. Manual reconciliation required."
            ),
            "provider": "simulated",
        }
    return {
        "ok": False,
        "error": "SEND_STATE",
        "plan_id": plan_id,
        "status": status,
        "message": f"Existing send record has status '{status}'. Provider not invoked.",
        "provider": "simulated",
    }


def send_notifications(
    plan_id: str,
    draft_hash: str | None = None,
    user_id: str = "user-alex",
) -> dict[str, Any]:
    """
    Send only with valid unexpired unconsumed hash-bound approval.

    Concurrency: only one caller may INSERT a (plan_id, content_hash) reservation
    with status 'sending'. Only that caller may dispatch the mock provider.
    """
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
            "message": (
                f"Cannot send notifications for plan with status '{plan['status']}'. "
                "Plan must be approved or executed first."
            ),
        }

    # --- Phase 1: validate + atomic reservation (BEGIN IMMEDIATE) ---
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        draft_row = conn.execute(
            """SELECT * FROM notification_drafts
               WHERE plan_id = ? AND user_id = ?
               ORDER BY created_at DESC LIMIT 1""",
            (plan_id, user_id),
        ).fetchone()
        if not draft_row:
            conn.rollback()
            return {"ok": False, "error": "NO_DRAFT", "message": "No notification draft found"}
        draft = dict(draft_row)

        if draft["content_hash"] != draft_hash:
            conn.rollback()
            return {
                "ok": False,
                "error": "HASH_MISMATCH",
                "message": "Submitted draft hash does not match stored draft.",
            }
        content_hash = draft_hash

        existing_send = conn.execute(
            "SELECT * FROM notification_sends WHERE plan_id = ? AND content_hash = ?",
            (plan_id, content_hash),
        ).fetchone()
        if existing_send:
            conn.rollback()
            return _response_for_existing_send(plan_id, dict(existing_send))

        approval_row = conn.execute(
            """SELECT * FROM notification_approvals
               WHERE plan_id = ? AND content_hash = ? AND approved_by = ?
                 AND consumed_at IS NULL
               ORDER BY approved_at DESC LIMIT 1""",
            (plan_id, content_hash, user_id),
        ).fetchone()
        if not approval_row:
            conn.rollback()
            return {
                "ok": False,
                "error": "NOT_APPROVED",
                "message": "No valid notification approval for this draft hash.",
            }
        approval = dict(approval_row)
        if approval.get("expires_at"):
            exp = datetime.fromisoformat(approval["expires_at"])
            if _now() > exp:
                conn.rollback()
                return {
                    "ok": False,
                    "error": "EXPIRED",
                    "message": "Notification approval has expired.",
                }

        send_id = _id()
        try:
            now = _now_iso()
            conn.execute(
                """INSERT INTO notification_sends
                   (id, plan_id, draft_id, content_hash, result_json, status, created_at, claimed_at)
                   VALUES (?, ?, ?, ?, ?, 'sending', ?, ?)""",
                (send_id, plan_id, draft["id"], content_hash, "[]", now, now),
            )
        except sqlite3.IntegrityError:
            # Lost the race — another worker reserved this (plan, hash)
            existing = conn.execute(
                "SELECT * FROM notification_sends WHERE plan_id = ? AND content_hash = ?",
                (plan_id, content_hash),
            ).fetchone()
            conn.rollback()
            if existing:
                return _response_for_existing_send(plan_id, dict(existing))
            return {
                "ok": False,
                "error": "CLAIM_FAILED",
                "message": "Could not claim send reservation.",
            }

        conn.execute(
            "UPDATE notification_approvals SET consumed_at = ? WHERE id = ?",
            (_now_iso(), approval["id"]),
        )
        conn.execute(
            "UPDATE notification_drafts SET status = 'sending' WHERE id = ?",
            (draft["id"],),
        )
        conn.commit()
        drafts = json.loads(draft["drafts_json"])
        draft_id = draft["id"]
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    # --- Phase 2: provider dispatch (only the winner reaches here) ---
    sent: list[dict] = []
    try:
        for d in drafts:
            result = message_provider.send_message({**d, "status": "draft"})
            sent.append(result)
    except Exception as e:
        # Outcome unknown after possible partial dispatch — do not invent success or retry
        with db_session() as c2:
            c2.execute(
                """UPDATE notification_sends
                   SET status = 'uncertain', result_json = ?
                   WHERE id = ?""",
                (json.dumps({"error": str(e), "partial": sent}), send_id),
            )
            c2.execute(
                "UPDATE notification_drafts SET status = 'uncertain' WHERE id = ?",
                (draft_id,),
            )
        return {
            "ok": False,
            "error": "SEND_UNCERTAIN",
            "plan_id": plan_id,
            "draft_id": draft_id,
            "status": "uncertain",
            "sent": sent,
            "message": (
                "Provider dispatch failed after reservation. Outcome uncertain; "
                "will not auto-retry. Manual check required."
            ),
            "provider": "simulated",
        }

    # --- Phase 3: finalize only if still 'sending' (lost race with reconcile → uncertain) ---
    with db_session() as c3:
        cur = c3.execute(
            """UPDATE notification_sends
               SET status = 'sent', result_json = ?
               WHERE id = ? AND status = 'sending'""",
            (json.dumps(sent), send_id),
        )
        if cur.rowcount != 1:
            # Reconcile or concurrent change won — do not claim success
            row = c3.execute(
                "SELECT status FROM notification_sends WHERE id = ?", (send_id,)
            ).fetchone()
            st = row["status"] if row else "unknown"
            return {
                "ok": False,
                "error": "SEND_UNCERTAIN" if st == "uncertain" else "FINALIZE_FAILED",
                "plan_id": plan_id,
                "draft_id": draft_id,
                "status": st,
                "sent": sent,
                "message": (
                    "Provider returned but DB finalization was not accepted "
                    f"(status={st}). Do not assume delivery state."
                ),
                "provider": "simulated",
            }
        c3.execute(
            "UPDATE notification_drafts SET status = 'sent' WHERE id = ?",
            (draft_id,),
        )

    return {
        "ok": True,
        "plan_id": plan_id,
        "draft_id": draft_id,
        "sent": sent,
        "status": "sent",
        "message": f"Sent {len(sent)} notification(s) via simulated mock provider.",
        "provider": "simulated",
    }



STALE_SEND_SECONDS = 120


def reconcile_stale_notification_send(
    plan_id: str,
    content_hash: str,
    user_id: str = "user-alex",
    stale_after_seconds: int = STALE_SEND_SECONDS,
) -> dict[str, Any]:
    """Mark a stale 'sending' reservation as uncertain. Never redispatches provider."""
    plan = repo.get_plan(plan_id)
    if not plan:
        return {"ok": False, "error": "PLAN_NOT_FOUND"}
    if plan["user_id"] != user_id:
        return {"ok": False, "error": "OWNERSHIP"}

    with db_session() as conn:
        row = conn.execute(
            "SELECT * FROM notification_sends WHERE plan_id = ? AND content_hash = ?",
            (plan_id, content_hash),
        ).fetchone()
        if not row:
            return {"ok": False, "error": "NO_SEND", "message": "No send reservation found"}
        es = dict(row)
        if es["status"] == "sent":
            return {"ok": True, "idempotent": True, "status": "sent", "message": "Already sent"}
        if es["status"] == "uncertain":
            return {
                "ok": False,
                "error": "SEND_UNCERTAIN",
                "status": "uncertain",
                "message": "Already uncertain; provider will not be retried automatically.",
            }
        if es["status"] != "sending":
            return {"ok": False, "error": "SEND_STATE", "status": es["status"]}

        claimed = es.get("claimed_at") or es.get("created_at")
        try:
            claimed_dt = datetime.fromisoformat(claimed) if claimed else None
        except ValueError:
            claimed_dt = None
        if claimed_dt is None or (_now() - claimed_dt).total_seconds() < stale_after_seconds:
            return {
                "ok": False,
                "error": "SEND_IN_PROGRESS",
                "status": "sending",
                "message": "Reservation still within lease; not reconciled.",
            }

        cur = conn.execute(
            """UPDATE notification_sends
               SET status = 'uncertain', result_json = ?
               WHERE id = ? AND status = 'sending'""",
            (json.dumps({"reconciled": True, "reason": "stale_lease"}), es["id"]),
        )
        if cur.rowcount != 1:
            return {
                "ok": False,
                "error": "CLAIM_FAILED",
                "message": "Could not reconcile; status may have changed concurrently.",
            }
        conn.execute(
            "UPDATE notification_drafts SET status = 'uncertain' WHERE id = ?",
            (es["draft_id"],),
        )

    return {
        "ok": True,
        "plan_id": plan_id,
        "status": "uncertain",
        "message": "Stale sending reservation marked uncertain. Provider was not redispatched.",
        "provider": "simulated",
    }
