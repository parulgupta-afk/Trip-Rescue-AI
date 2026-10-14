"""Execution service – saga-style, idempotent, with compensation."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from server.store.database import db_session
from server.store import repositories as repo
from server.domain import approval_service
from server.providers import hotel_provider, ride_provider, message_provider


# In-memory switch for deterministic failure demo (set via tool or env)
FORCE_FAIL_STEP: str | None = None  # e.g. "reschedule_ride"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id() -> str:
    return str(uuid.uuid4())


def set_force_fail(step: str | None) -> None:
    global FORCE_FAIL_STEP
    FORCE_FAIL_STEP = step


def execute_plan(
    plan_id: str,
    user_id: str = "user-alex",
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """
    Execute an approved plan.
    - Verifies approval (hash, ownership, expiry)
    - Runs steps in order (flight → hotel → ride → notification)
    - Compensates on failure where possible
    - Idempotent via plan status + optional key
    """
    plan = repo.get_plan(plan_id)
    if not plan:
        return {"ok": False, "error": "PLAN_NOT_FOUND", "message": f"Plan {plan_id} not found"}

    if plan["user_id"] != user_id:
        return {"ok": False, "error": "OWNERSHIP", "message": "Plan does not belong to this user"}

    # Idempotency: already finished
    if plan["status"] in ("succeeded", "failed_rolled_back", "partially_failed"):
        steps = _get_steps(plan_id)
        return {
            "ok": True,
            "idempotent": True,
            "plan_id": plan_id,
            "status": plan["status"],
            "steps": steps,
            "message": f"Plan already in terminal state '{plan['status']}'. Returning previous result.",
        }

    if plan["status"] not in ("approved", "executing"):
        return {
            "ok": False,
            "error": "NOT_APPROVED",
            "message": f"Plan status is '{plan['status']}'. Approve the plan before execution.",
        }

    approval = approval_service.get_valid_approval(plan_id, user_id)
    if not approval:
        return {
            "ok": False,
            "error": "NO_VALID_APPROVAL",
            "message": "No valid (unexpired, unconsumed) approval found for this plan.",
        }

    # Re-check hash
    if approval["plan_hash"] != plan["plan_hash"]:
        return {
            "ok": False,
            "error": "HASH_MISMATCH",
            "message": "Approval hash does not match current plan. Re-approve.",
        }

    # Atomic claim: only one worker may move approved → executing
    with db_session() as conn:
        cur = conn.execute(
            "UPDATE plans SET status = 'executing' WHERE id = ? AND status = 'approved'",
            (plan_id,),
        )
        if cur.rowcount != 1:
            # Another request claimed it, or status changed
            current = repo.get_plan(plan_id)
            st = (current or {}).get("status")
            if st in ("succeeded", "failed_rolled_back", "partially_failed", "executing"):
                steps = _get_steps(plan_id)
                return {
                    "ok": True,
                    "idempotent": True,
                    "plan_id": plan_id,
                    "status": st,
                    "steps": steps,
                    "message": f"Plan already claimed or finished (status={st}).",
                }
            return {
                "ok": False,
                "error": "CLAIM_FAILED",
                "message": f"Could not claim plan for execution (status={st}).",
            }
    approval_service.consume_approval(approval["id"])

    actions = plan["actions"]
    results: list[dict] = []
    failed = False
    fail_index = -1

    for i, action in enumerate(actions):
        step_id = _id()
        action_type = action["type"]
        started = _now_iso()

        # Force-fail hook for demo
        if FORCE_FAIL_STEP and action_type == FORCE_FAIL_STEP:
            result = {
                "status": "failed",
                "error_code": "PROVIDER_FAILURE",
                "message": f"Simulated failure on {action_type}",
            }
            _record_step(plan_id, i + 1, action_type, "failed", result, "PROVIDER_FAILURE", started)
            results.append({"step": i + 1, "type": action_type, **result})
            failed = True
            fail_index = i
            break

        try:
            result = _run_action(action)
            status = result.get("status", "success")
            _record_step(plan_id, i + 1, action_type, status, result, None, started)
            results.append({"step": i + 1, "type": action_type, **result})
            if status == "failed":
                failed = True
                fail_index = i
                break
        except Exception as e:
            result = {"status": "failed", "error_code": "EXCEPTION", "message": str(e)}
            _record_step(plan_id, i + 1, action_type, "failed", result, "EXCEPTION", started)
            results.append({"step": i + 1, "type": action_type, **result})
            failed = True
            fail_index = i
            break

    if not failed:
        with db_session() as conn:
            conn.execute("UPDATE plans SET status = 'succeeded' WHERE id = ?", (plan_id,))
        return {
            "ok": True,
            "plan_id": plan_id,
            "status": "succeeded",
            "steps": results,
            "message": "All recovery actions completed successfully.",
        }

    # Compensation for completed steps before the failure
    compensations: list[dict] = []
    for j in range(fail_index - 1, -1, -1):
        prev = actions[j]
        comp = _compensate_action(prev)
        if comp:
            _record_step(
                plan_id, j + 1, f"compensate_{prev['type']}",
                comp.get("status", "compensated"), comp, None, _now_iso(),
            )
            compensations.append(comp)

    final_status = "failed_rolled_back" if compensations else "partially_failed"
    # Notifications cannot be unsent → always partially_failed if a notification succeeded earlier
    if any(r.get("type") == "draft_notification" and r.get("status") == "sent" for r in results):
        final_status = "partially_failed"

    with db_session() as conn:
        conn.execute("UPDATE plans SET status = ? WHERE id = ?", (final_status, plan_id))

    return {
        "ok": False,
        "plan_id": plan_id,
        "status": final_status,
        "steps": results,
        "compensations": compensations,
        "message": f"Execution failed at step {fail_index + 1}. Status: {final_status}.",
    }


def _run_action(action: dict) -> dict[str, Any]:
    t = action["type"]
    if t == "change_flight":
        return {
            "status": "success",
            "target": action["target"],
            "flight_number": action.get("flight_number"),
            "message": f"Flight changed to {action.get('flight_number')}",
        }
    if t == "reschedule_hotel":
        return hotel_provider.apply_checkin_change(
            action["target"], action["proposed_check_in"]
        )
    if t == "reschedule_ride":
        return ride_provider.apply_reschedule(
            action["target"], action["proposed_pickup"]
        )
    if t == "draft_notification":
        # In real flow we would require a second approval; for demo we mark as ready
        return {
            "status": "success",
            "recipient": action.get("recipient"),
            "body": action.get("body"),
            "message": "Notification draft ready (not sent until send_notifications)",
        }
    return {"status": "success", "message": f"Unhandled action type {t} (noop)"}


def _compensate_action(action: dict) -> dict[str, Any] | None:
    t = action["type"]
    if t == "change_flight":
        return {
            "status": "compensated",
            "type": "change_flight",
            "message": "Flight restored to original booking",
        }
    if t == "reschedule_hotel":
        return hotel_provider.compensate_checkin(
            action["target"], action["original_check_in"]
        )
    if t == "reschedule_ride":
        return ride_provider.compensate_reschedule(
            action["target"], action["original_pickup"]
        )
    if t == "draft_notification":
        return None  # cannot unsend
    return None


def _record_step(
    plan_id: str,
    step_number: int,
    action_type: str,
    status: str,
    result: dict,
    error_code: str | None,
    started_at: str,
) -> None:
    with db_session() as conn:
        conn.execute(
            """INSERT INTO execution_steps
               (id, plan_id, step_number, action_type, status, result_json, error_code, started_at, completed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                _id(), plan_id, step_number, action_type, status,
                json.dumps(result), error_code, started_at, _now_iso(),
            ),
        )


def _get_steps(plan_id: str) -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM execution_steps WHERE plan_id = ? ORDER BY step_number, completed_at",
            (plan_id,),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["result"] = json.loads(d["result_json"]) if d["result_json"] else None
            out.append(d)
        return out


def get_plan_status(plan_id: str) -> dict[str, Any]:
    plan = repo.get_plan(plan_id)
    if not plan:
        return {"error": f"Plan {plan_id} not found"}
    steps = _get_steps(plan_id)
    return {
        "plan_id": plan_id,
        "status": plan["status"],
        "version": plan["version"],
        "total_cost_delta": plan["total_cost_delta"],
        "plan_hash": plan["plan_hash"],
        "steps": steps,
    }


def recover_stuck_execution(plan_id: str, user_id: str = "user-alex") -> dict[str, Any]:
    """
    Recover a plan stuck in 'executing' after interruption.

    - Ownership and status validated.
    - Atomic transition: only succeeds if status is still 'executing'.
    - Each planned action is identified by step_number (1-based index).
    - Steps with no terminal record are marked 'interrupted' (unknown outcome).
    - Never invents success or retries providers.
    """
    plan = repo.get_plan(plan_id)
    if not plan:
        return {"ok": False, "error": "PLAN_NOT_FOUND", "message": f"Plan {plan_id} not found"}
    if plan["user_id"] != user_id:
        return {"ok": False, "error": "OWNERSHIP", "message": "Plan does not belong to this user"}
    if plan["status"] != "executing":
        return {
            "ok": True,
            "idempotent": True,
            "plan_id": plan_id,
            "status": plan["status"],
            "steps": _get_steps(plan_id),
            "message": f"Plan is not stuck in executing (status={plan['status']}).",
        }

    actions = plan.get("actions") or []
    existing = _get_steps(plan_id)
    # Map step_number -> last record
    by_num: dict[int, dict] = {}
    for s in existing:
        by_num[int(s["step_number"])] = s

    interrupted: list[dict] = []
    for i, action in enumerate(actions):
        step_number = i + 1
        action_type = action.get("type", "unknown")
        step_key = f"{plan_id}:step:{step_number}:{action_type}"
        rec = by_num.get(step_number)
        if rec is None:
            result = {
                "status": "interrupted",
                "step_id": step_key,
                "message": "No terminal provider result recorded before interruption.",
            }
            _record_step(
                plan_id, step_number, action_type, "interrupted", result, "INTERRUPTED", _now_iso()
            )
            interrupted.append({"step_number": step_number, "type": action_type, "step_id": step_key})
        elif rec.get("status") in ("pending", "running", "executing"):
            result = {
                "status": "interrupted",
                "step_id": step_key,
                "prior_status": rec.get("status"),
                "message": "Step had non-terminal status at recovery time.",
            }
            _record_step(
                plan_id, step_number, action_type, "interrupted", result, "INTERRUPTED", _now_iso()
            )
            interrupted.append({"step_number": step_number, "type": action_type, "step_id": step_key})

    with db_session() as conn:
        cur = conn.execute(
            "UPDATE plans SET status = 'partially_failed' WHERE id = ? AND status = 'executing'",
            (plan_id,),
        )
        claimed = cur.rowcount == 1

    if not claimed:
        current = repo.get_plan(plan_id)
        return {
            "ok": True,
            "idempotent": True,
            "plan_id": plan_id,
            "status": (current or {}).get("status"),
            "steps": _get_steps(plan_id),
            "message": "Concurrent status change: plan is no longer executing.",
        }

    steps = _get_steps(plan_id)
    return {
        "ok": True,
        "plan_id": plan_id,
        "status": "partially_failed",
        "interrupted_steps": interrupted,
        "steps": steps,
        "message": (
            "Plan left in executing was marked partially_failed. "
            f"{len(interrupted)} step(s) recorded as interrupted (unknown outcome). "
            "Providers were not retried; do not assume success."
        ),
        "provider": "simulated",
    }
