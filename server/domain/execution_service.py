"""Execution service – saga-style, idempotent, with compensation."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
import threading
from typing import Any, Callable

from server.store.database import db_session, get_connection
from server.store import repositories as repo
from server.domain import approval_service
from server.providers import hotel_provider, ride_provider, message_provider


# In-memory switch for deterministic failure demo (set via tool or env)
FORCE_FAIL_STEP: str | None = None  # e.g. "reschedule_ride"

# Test hooks for controlled concurrency verification
_before_action_hook: Callable[[int, str], None] | None = None
_before_compensation_hook: Callable[[dict], None] | None = None


def set_before_action_hook(fn: Callable[[int, str], None] | None) -> None:
    global _before_action_hook
    _before_action_hook = fn


def set_before_compensation_hook(fn: Callable[[dict], None] | None) -> None:
    global _before_compensation_hook
    _before_compensation_hook = fn


def reset_execution_hooks() -> None:
    global _before_action_hook, _before_compensation_hook
    _before_action_hook = None
    _before_compensation_hook = None


def _now() -> datetime:
    return datetime.now(timezone.utc)

def _now_iso() -> str:
    return _now().isoformat()


def _id() -> str:
    return str(uuid.uuid4())


def set_force_fail(step: str | None) -> None:
    global FORCE_FAIL_STEP
    FORCE_FAIL_STEP = step


def _verify_claim(plan_id: str, worker_id: str) -> bool:
    """Verify that plan is still executing and the claim is held by worker_id."""
    with db_session() as conn:
        plan_row = conn.execute(
            "SELECT status FROM plans WHERE id = ?", (plan_id,)
        ).fetchone()
        if not plan_row or plan_row["status"] != "executing":
            return False
        claim = conn.execute(
            "SELECT worker_id FROM execution_claims WHERE plan_id = ?", (plan_id,)
        ).fetchone() if _table_exists(conn, "execution_claims") else None
        if not claim or claim["worker_id"] != worker_id:
            return False
        return True


def _renew_claim(plan_id: str, worker_id: str) -> bool:
    """Verify ownership and renew the lease timestamp in execution_claims."""
    with db_session() as conn:
        plan_row = conn.execute(
            "SELECT status FROM plans WHERE id = ?", (plan_id,)
        ).fetchone()
        if not plan_row or plan_row["status"] != "executing":
            return False
        cur = conn.execute(
            "UPDATE execution_claims SET claimed_at = ? WHERE plan_id = ? AND worker_id = ?",
            (_now_iso(), plan_id, worker_id),
        )
        return cur.rowcount == 1


class LeaseHeartbeat:
    """Periodically renews execution claim lease during potentially slow operations."""
    def __init__(self, plan_id: str, worker_id: str, interval: float = 1.0):
        self.plan_id = plan_id
        self.worker_id = worker_id
        self.interval = interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self.lost_ownership = False

    def _run(self) -> None:
        while not self._stop_event.wait(self.interval):
            if not _renew_claim(self.plan_id, self.worker_id):
                self.lost_ownership = True
                break

    def __enter__(self) -> LeaseHeartbeat:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)


def execute_plan(
    plan_id: str,
    user_id: str = "user-alex",
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """
    Execute an approved plan.
    - Verifies approval (hash, ownership, expiry)
    - Retains atomic worker ownership throughout execution
    - Runs steps in order (flight → hotel → ride → notification)
    - Continuously renews lease and halts if ownership is lost
    - Compensates on failure only while worker retains ownership
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

    # Atomic claim: only one worker may move approved → executing and record its worker_id
    worker_id = _id()
    with db_session() as conn:
        cur = conn.execute(
            "UPDATE plans SET status = 'executing' WHERE id = ? AND status = 'approved'",
            (plan_id,),
        )
        if cur.rowcount == 1:
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO execution_claims (plan_id, claimed_at, worker_id) VALUES (?, ?, ?)",
                    (plan_id, _now_iso(), worker_id),
                )
            except Exception:
                pass  # table may not exist until migrate
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

        # Verify and renew claim before starting step
        if not _renew_claim(plan_id, worker_id):
            return {
                "ok": False,
                "error": "OWNERSHIP_LOST",
                "plan_id": plan_id,
                "status": (repo.get_plan(plan_id) or {}).get("status"),
                "steps": results,
                "message": f"Worker lost ownership before starting step {i + 1} ({action_type}).",
            }

        hook = _before_action_hook
        if hook:
            hook(i + 1, action_type)

        # Force-fail hook for demo
        if FORCE_FAIL_STEP and action_type == FORCE_FAIL_STEP:
            result = {
                "status": "failed",
                "error_code": "PROVIDER_FAILURE",
                "message": f"Simulated failure on {action_type}",
            }
            if not _verify_claim(plan_id, worker_id):
                return {
                    "ok": False,
                    "error": "OWNERSHIP_LOST",
                    "plan_id": plan_id,
                    "status": (repo.get_plan(plan_id) or {}).get("status"),
                    "steps": results,
                    "message": "Worker lost ownership during step execution.",
                }
            _record_step(plan_id, i + 1, action_type, "failed", result, "PROVIDER_FAILURE", started)
            results.append({"step": i + 1, "type": action_type, **result})
            failed = True
            fail_index = i
            break

        try:
            with LeaseHeartbeat(plan_id, worker_id, interval=0.5) as heartbeat:
                result = _run_action(action)
            if heartbeat.lost_ownership or not _renew_claim(plan_id, worker_id):
                return {
                    "ok": False,
                    "error": "OWNERSHIP_LOST",
                    "plan_id": plan_id,
                    "status": (repo.get_plan(plan_id) or {}).get("status"),
                    "steps": results,
                    "message": f"Worker lost ownership during execution of step {i + 1} ({action_type}).",
                }
            status = result.get("status", "success")
            _record_step(plan_id, i + 1, action_type, status, result, None, started)
            results.append({"step": i + 1, "type": action_type, **result})
            if status == "failed":
                failed = True
                fail_index = i
                break
        except Exception as e:
            if not _verify_claim(plan_id, worker_id):
                return {
                    "ok": False,
                    "error": "OWNERSHIP_LOST",
                    "plan_id": plan_id,
                    "status": (repo.get_plan(plan_id) or {}).get("status"),
                    "steps": results,
                    "message": "Worker lost ownership during step execution.",
                }
            result = {"status": "failed", "error_code": "EXCEPTION", "message": str(e)}
            _record_step(plan_id, i + 1, action_type, "failed", result, "EXCEPTION", started)
            results.append({"step": i + 1, "type": action_type, **result})
            failed = True
            fail_index = i
            break

    if not failed:
        with db_session() as conn:
            claim = conn.execute(
                "SELECT worker_id FROM execution_claims WHERE plan_id = ?", (plan_id,)
            ).fetchone() if _table_exists(conn, "execution_claims") else None
            if not claim or claim["worker_id"] != worker_id:
                return {
                    "ok": False,
                    "error": "OWNERSHIP_LOST",
                    "plan_id": plan_id,
                    "status": (repo.get_plan(plan_id) or {}).get("status"),
                    "steps": results,
                    "message": "Worker lost ownership before finalizing success.",
                }
            cur = conn.execute(
                "UPDATE plans SET status = 'succeeded' WHERE id = ? AND status = 'executing'",
                (plan_id,),
            )
            if cur.rowcount != 1:
                return {
                    "ok": False,
                    "error": "OWNERSHIP_LOST",
                    "plan_id": plan_id,
                    "status": (repo.get_plan(plan_id) or {}).get("status"),
                    "steps": results,
                    "message": "Worker lost ownership before finalizing success.",
                }
            if _table_exists(conn, "execution_claims"):
                conn.execute("DELETE FROM execution_claims WHERE plan_id = ? AND worker_id = ?", (plan_id, worker_id))
        return {
            "ok": True,
            "plan_id": plan_id,
            "status": "succeeded",
            "steps": results,
            "message": "All recovery actions completed successfully.",
        }

    # Verify claim ownership before running any compensations
    if not _verify_claim(plan_id, worker_id):
        return {
            "ok": False,
            "error": "OWNERSHIP_LOST",
            "plan_id": plan_id,
            "status": (repo.get_plan(plan_id) or {}).get("status"),
            "steps": results,
            "message": "Worker lost ownership before compensation; compensation skipped.",
        }

    # Compensation for completed steps before the failure
    compensations: list[dict] = []
    for j in range(fail_index - 1, -1, -1):
        prev = actions[j]
        # Check claim ownership before each compensation step
        if not _renew_claim(plan_id, worker_id):
            return {
                "ok": False,
                "error": "OWNERSHIP_LOST",
                "plan_id": plan_id,
                "status": (repo.get_plan(plan_id) or {}).get("status"),
                "steps": results,
                "compensations": compensations,
                "message": f"Worker lost ownership before compensating step {j + 1}.",
            }
        comp_hook = _before_compensation_hook
        if comp_hook:
            comp_hook(prev)
        with LeaseHeartbeat(plan_id, worker_id, interval=0.5) as heartbeat:
            comp = _compensate_action(prev)
        if heartbeat.lost_ownership or not _renew_claim(plan_id, worker_id):
            return {
                "ok": False,
                "error": "OWNERSHIP_LOST",
                "plan_id": plan_id,
                "status": (repo.get_plan(plan_id) or {}).get("status"),
                "steps": results,
                "compensations": compensations,
                "message": f"Worker lost ownership during compensation of step {j + 1}.",
            }
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
        claim = conn.execute(
            "SELECT worker_id FROM execution_claims WHERE plan_id = ?", (plan_id,)
        ).fetchone() if _table_exists(conn, "execution_claims") else None
        if not claim or claim["worker_id"] != worker_id:
            return {
                "ok": False,
                "error": "OWNERSHIP_LOST",
                "plan_id": plan_id,
                "status": (repo.get_plan(plan_id) or {}).get("status"),
                "steps": results,
                "compensations": compensations,
                "message": "Execution worker lost ownership before finalizing failure status.",
            }
        cur = conn.execute(
            "UPDATE plans SET status = ? WHERE id = ? AND status = 'executing'",
            (final_status, plan_id),
        )
        if cur.rowcount != 1:
            return {
                "ok": False,
                "error": "OWNERSHIP_LOST",
                "plan_id": plan_id,
                "status": (repo.get_plan(plan_id) or {}).get("status"),
                "steps": results,
                "compensations": compensations,
                "message": "Execution worker lost ownership before finalizing failure status.",
            }
        if _table_exists(conn, "execution_claims"):
            conn.execute("DELETE FROM execution_claims WHERE plan_id = ? AND worker_id = ?", (plan_id, worker_id))

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


def get_plan_status(plan_id: str, user_id: str = "user-alex") -> dict[str, Any]:
    plan = repo.get_plan(plan_id)
    if not plan:
        return {"ok": False, "error": "PLAN_NOT_FOUND", "message": f"Plan {plan_id} not found"}
    if plan["user_id"] != user_id:
        return {"ok": False, "error": "OWNERSHIP", "message": "Plan does not belong to this user"}
    steps = _get_steps(plan_id)
    return {
        "ok": True,
        "plan_id": plan_id,
        "status": plan["status"],
        "version": plan["version"],
        "total_cost_delta": plan["total_cost_delta"],
        "plan_hash": plan["plan_hash"],
        "actions": plan.get("actions"),
        "steps": steps,
    }


MIN_RECOVERY_STALE_SECONDS = 30
DEFAULT_RECOVERY_STALE_SECONDS = 120


def recover_stuck_execution(
    plan_id: str,
    user_id: str = "user-alex",
    stale_after_seconds: int = DEFAULT_RECOVERY_STALE_SECONDS,
    *,
    _force_for_test: bool = False,
    _min_threshold_override: int | None = None,
) -> dict[str, Any]:
    """
    Recover abandoned executions only.

    1. Ownership check
    2. Plan must be 'executing'
    3. Must be stale (no recent step activity / claim older than lease). Force recovery is restricted to internal tests.
    4. Atomic claim to partially_failed in same transaction as interrupted step inserts
    5. Losers write nothing
    """
    min_thresh = _min_threshold_override if _min_threshold_override is not None else MIN_RECOVERY_STALE_SECONDS
    if not _force_for_test:
        if stale_after_seconds <= 0:
            return {
                "ok": False,
                "error": "INVALID_ARGUMENT",
                "message": "stale_after_seconds must be a positive integer.",
            }
        if stale_after_seconds < min_thresh:
            return {
                "ok": False,
                "error": "INVALID_ARGUMENT",
                "message": f"stale_after_seconds cannot be shorter than server lease threshold ({min_thresh}s).",
            }

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

    steps_before = _get_steps(plan_id)
    # Stale detection: use latest step completed_at or plan-level executing claim marker
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT status, user_id FROM plans WHERE id = ?", (plan_id,)).fetchone()
        if not row or row["status"] != "executing" or row["user_id"] != user_id:
            conn.rollback()
            current = repo.get_plan(plan_id)
            return {
                "ok": True,
                "idempotent": True,
                "plan_id": plan_id,
                "status": (current or {}).get("status"),
                "steps": _get_steps(plan_id),
                "message": "Recovery did not claim; plan no longer executing.",
            }

        # Lease: check execution_claims if present, else step timestamps
        claim = conn.execute(
            "SELECT claimed_at, worker_id FROM execution_claims WHERE plan_id = ?", (plan_id,)
        ).fetchone() if _table_exists(conn, "execution_claims") else None
        last_step = conn.execute(
            "SELECT MAX(completed_at) AS ts FROM execution_steps WHERE plan_id = ?",
            (plan_id,),
        ).fetchone()
        ref_ts = None
        if claim and claim["claimed_at"]:
            ref_ts = claim["claimed_at"]
        elif last_step and last_step["ts"]:
            ref_ts = last_step["ts"]

        # If staleness cannot be established and not an internal force test, fail closed
        if not _force_for_test:
            if not ref_ts:
                conn.rollback()
                return {
                    "ok": False,
                    "error": "CANNOT_ESTABLISH_STALENESS",
                    "plan_id": plan_id,
                    "status": "executing",
                    "message": "Missing claim or timestamp information; cannot safely determine staleness.",
                }
            try:
                claimed_dt = datetime.fromisoformat(ref_ts)
                if claimed_dt.tzinfo is None:
                    claimed_dt = claimed_dt.replace(tzinfo=timezone.utc)
                age = (_now() - claimed_dt).total_seconds()
            except ValueError:
                conn.rollback()
                return {
                    "ok": False,
                    "error": "CANNOT_ESTABLISH_STALENESS",
                    "plan_id": plan_id,
                    "status": "executing",
                    "message": "Invalid timestamp format; cannot safely determine staleness.",
                }
            if age < stale_after_seconds:
                conn.rollback()
                return {
                    "ok": False,
                    "error": "EXECUTION_ACTIVE",
                    "plan_id": plan_id,
                    "status": "executing",
                    "message": "Execution appears active (within lease). Recovery refused.",
                }

        cur = conn.execute(
            "UPDATE plans SET status = 'partially_failed' WHERE id = ? AND status = 'executing'",
            (plan_id,),
        )
        if cur.rowcount != 1:
            conn.rollback()
            current = repo.get_plan(plan_id)
            return {
                "ok": True,
                "idempotent": True,
                "plan_id": plan_id,
                "status": (current or {}).get("status"),
                "steps": _get_steps(plan_id),
                "message": "Lost recovery race; no step records written.",
            }

        actions = plan.get("actions") or []
        existing = {
            int(r["step_number"]): dict(r)
            for r in conn.execute(
                "SELECT * FROM execution_steps WHERE plan_id = ?", (plan_id,)
            ).fetchall()
        }
        interrupted = []
        terminal = {"success", "failed", "compensated", "interrupted", "uncertain"}
        for i, action in enumerate(actions):
            step_number = i + 1
            action_type = action.get("type", "unknown")
            step_key = f"{plan_id}:step:{step_number}:{action_type}"
            rec = existing.get(step_number)
            if rec is None or rec.get("status") not in terminal:
                result_json = json.dumps({
                    "status": "interrupted",
                    "step_id": step_key,
                    "message": "No terminal provider result before recovery.",
                })
                conn.execute(
                    """INSERT INTO execution_steps
                       (id, plan_id, step_number, action_type, status, result_json, error_code, started_at, completed_at)
                       VALUES (?, ?, ?, ?, 'interrupted', ?, 'INTERRUPTED', ?, ?)""",
                    (_id(), plan_id, step_number, action_type, result_json, _now_iso(), _now_iso()),
                )
                interrupted.append({"step_number": step_number, "type": action_type, "step_id": step_key})
        if _table_exists(conn, "execution_claims"):
            conn.execute("DELETE FROM execution_claims WHERE plan_id = ?", (plan_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    steps = _get_steps(plan_id)
    return {
        "ok": True,
        "plan_id": plan_id,
        "status": "partially_failed",
        "interrupted_steps": interrupted,
        "steps": steps,
        "message": (
            f"Recovered abandoned execution. {len(interrupted)} step(s) marked interrupted. "
            "Providers not retried."
        ),
        "provider": "simulated",
    }


def _table_exists(conn, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def force_recover_for_test(plan_id: str, user_id: str = "user-alex") -> dict[str, Any]:
    """Internal test helper ONLY: force recovery to test race handling when a worker loses ownership."""
    return recover_stuck_execution(plan_id, user_id, stale_after_seconds=0, _force_for_test=True)

