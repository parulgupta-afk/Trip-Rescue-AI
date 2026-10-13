"""Notification + memory tests (Phase 5)."""
from server.store.database import init_db
from server.store import repositories as repo
from server.tools import trip_tools
from server.domain import execution_service


def setup_function():
    init_db()
    repo.seed_demo_data()
    execution_service.set_force_fail(None)


def test_send_without_approval_rejected():
    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    trip_tools.approve_rescue_plan(plan["plan_id"], plan["plan_hash"])
    trip_tools.execute_rescue_plan(plan["plan_id"])
    result = trip_tools.send_notifications(plan["plan_id"], approved=False)
    assert result["ok"] is False
    assert result["error"] == "NOT_APPROVED"


def test_draft_and_send_with_approval():
    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    trip_tools.approve_rescue_plan(plan["plan_id"], plan["plan_hash"])
    trip_tools.execute_rescue_plan(plan["plan_id"])
    drafts = trip_tools.draft_notifications(plan["plan_id"])
    assert "drafts" in drafts
    assert len(drafts["drafts"]) >= 1
    sent = trip_tools.send_notifications(plan["plan_id"], approved=True)
    assert sent["ok"] is True
    assert len(sent["sent"]) >= 1


def test_preference_memory():
    before = trip_tools.list_preferences()
    assert before["count"] >= 1
    trip_tools.save_preference("seat", "window")
    after = trip_tools.get_preferences()
    assert after["seat"]["value"] == "window"
