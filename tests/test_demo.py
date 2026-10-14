"""Deterministic demo orchestrator uses real tools."""
from server.store.bootstrap import ensure_schema
from server.store import repositories as repo
from server.domain import execution_service
from agent.orchestrator import run_demo
import server.tools.trip_tools as tt


def test_run_demo_happy_path():
    ensure_schema()
    repo.seed_demo_data(wipe=True)
    execution_service.set_force_fail(None)
    tt._initialized = True
    log = run_demo("FLIGHT-A")
    names = [s["tool"] for s in log]
    assert "get_trip" in names
    assert "execute_rescue_plan" in names
    assert "approve_notifications" in names
    assert "send_notifications" in names
    assert len(log) >= 9
    send = next(s for s in log if s["tool"] == "send_notifications")
    assert "error" not in send["result_summary"] or "sent" in send["result_summary"]
