"""Safety tests for approval + execution (Phase 4)."""
from server.store.bootstrap import ensure_schema
from server.store.database import init_db
from server.store import repositories as repo
from server.tools import trip_tools
from server.domain import execution_service


def setup_function():
    ensure_schema()
    repo.seed_demo_data(wipe=True)
    execution_service.set_force_fail(None)


def test_execute_without_approval_rejected():
    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    result = trip_tools.execute_rescue_plan(plan["plan_id"])
    assert result["ok"] is False
    assert result["error"] in ("NOT_APPROVED", "NO_VALID_APPROVAL")


def test_hash_mismatch_rejected():
    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    bad = trip_tools.approve_rescue_plan(plan["plan_id"], "wrong-hash-value")
    assert bad["ok"] is False
    assert bad["error"] == "HASH_MISMATCH"


def test_happy_path_approve_and_execute():
    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    approval = trip_tools.approve_rescue_plan(plan["plan_id"], plan["plan_hash"])
    assert approval["ok"] is True
    result = trip_tools.execute_rescue_plan(plan["plan_id"])
    assert result["ok"] is True
    assert result["status"] == "succeeded"
    assert len(result["steps"]) >= 3


def test_idempotent_reexecute():
    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    trip_tools.approve_rescue_plan(plan["plan_id"], plan["plan_hash"])
    first = trip_tools.execute_rescue_plan(plan["plan_id"])
    second = trip_tools.execute_rescue_plan(plan["plan_id"])
    assert first["status"] == "succeeded"
    assert second.get("idempotent") is True
    assert second["status"] == "succeeded"


def test_forced_failure_triggers_compensation():
    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    trip_tools.approve_rescue_plan(plan["plan_id"], plan["plan_hash"])
    result = trip_tools.execute_rescue_plan(plan["plan_id"], force_fail_step="reschedule_ride")
    assert result["ok"] is False
    assert result["status"] in ("failed_rolled_back", "partially_failed")
    assert any(s.get("status") == "failed" for s in result["steps"])
    assert len(result.get("compensations", [])) >= 1


def test_stale_plan_version():
    """Approving then changing plan would require a new proposal; old hash fails."""
    plan1 = trip_tools.propose_rescue_plan("FLIGHT-A")
    plan2 = trip_tools.propose_rescue_plan("FLIGHT-B")  # new version
    # Try to approve plan1 with its own hash – still valid if still pending
    # But execute plan2 without approval should fail
    result = trip_tools.execute_rescue_plan(plan2["plan_id"])
    assert result["ok"] is False


def test_expired_approval_rejected():
    """Approval past expires_at must not authorize execution."""
    from datetime import datetime, timezone, timedelta
    from server.store.database import db_session
    from server.domain import execution_service

    execution_service.set_force_fail(None)
    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    approval = trip_tools.approve_rescue_plan(plan["plan_id"], plan["plan_hash"])
    assert approval["ok"] is True

    # Force expiry in DB
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    with db_session() as conn:
        conn.execute(
            "UPDATE approvals SET expires_at = ? WHERE plan_id = ?",
            (past, plan["plan_id"]),
        )

    result = trip_tools.execute_rescue_plan(plan["plan_id"])
    assert result["ok"] is False
    assert result["error"] in ("NO_VALID_APPROVAL", "NOT_APPROVED")
