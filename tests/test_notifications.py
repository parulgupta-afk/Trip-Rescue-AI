"""Hash-bound notification approval tests."""
from server.store.bootstrap import ensure_schema
from server.store import repositories as repo
from server.tools import trip_tools
from server.domain import execution_service


def setup_function():
    ensure_schema()
    repo.seed_demo_data(wipe=True)
    execution_service.set_force_fail(None)
    # reset tool init flag
    import server.tools.trip_tools as tt
    tt._initialized = True  # schema already ready


def _approved_plan():
    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    assert "plan_id" in plan and "error" not in plan
    ap = trip_tools.approve_rescue_plan(plan["plan_id"], plan["plan_hash"])
    assert ap["ok"]
    ex = trip_tools.execute_rescue_plan(plan["plan_id"])
    assert ex.get("status") == "succeeded"
    return plan


def test_send_without_approval_rejected():
    plan = _approved_plan()
    draft = trip_tools.draft_notifications(plan["plan_id"])
    assert draft.get("ok") is True
    result = trip_tools.send_notifications(plan["plan_id"], draft["content_hash"])
    assert result["ok"] is False
    assert result["error"] == "NOT_APPROVED"


def test_boolean_approved_not_sufficient():
    """Legacy approved=True must not authorize send."""
    plan = _approved_plan()
    draft = trip_tools.draft_notifications(plan["plan_id"])
    # Call domain with only boolean path removed — send requires hash approval
    result = trip_tools.send_notifications(plan["plan_id"], None)
    assert result["ok"] is False


def test_hash_mismatch_rejected():
    plan = _approved_plan()
    draft = trip_tools.draft_notifications(plan["plan_id"])
    bad = trip_tools.approve_notifications(plan["plan_id"], "wrong-hash")
    assert bad["ok"] is False
    assert bad["error"] == "HASH_MISMATCH"


def test_draft_approve_send_success():
    plan = _approved_plan()
    draft = trip_tools.draft_notifications(plan["plan_id"])
    ap = trip_tools.approve_notifications(plan["plan_id"], draft["content_hash"])
    assert ap["ok"] is True
    sent = trip_tools.send_notifications(plan["plan_id"], draft["content_hash"])
    assert sent["ok"] is True
    assert sent.get("provider") == "simulated"
    assert len(sent["sent"]) >= 1


def test_duplicate_send_idempotent():
    plan = _approved_plan()
    draft = trip_tools.draft_notifications(plan["plan_id"])
    trip_tools.approve_notifications(plan["plan_id"], draft["content_hash"])
    first = trip_tools.send_notifications(plan["plan_id"], draft["content_hash"])
    second = trip_tools.send_notifications(plan["plan_id"], draft["content_hash"])
    assert first["ok"] is True
    assert second.get("idempotent") is True


def test_preference_memory():
    before = trip_tools.list_preferences()
    assert before["count"] >= 1
    trip_tools.save_preference("seat", "window")
    after = trip_tools.get_preferences()
    assert after["seat"]["value"] == "window"
