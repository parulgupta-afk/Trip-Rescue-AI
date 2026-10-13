"""Deterministic demo orchestrator uses real tools."""
from server.store.database import init_db
from server.store import repositories as repo
from server.domain import execution_service
from agent.orchestrator import run_demo


def test_run_demo_happy_path():
    init_db()
    repo.seed_demo_data()
    execution_service.set_force_fail(None)
    log = run_demo("FLIGHT-A")
    names = [s["tool"] for s in log]
    assert "get_trip" in names
    assert "execute_rescue_plan" in names
    assert "send_notifications" in names
    assert len(log) >= 9
