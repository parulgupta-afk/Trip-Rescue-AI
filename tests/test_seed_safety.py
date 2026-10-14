"""Imports and restarts must not wipe persisted data."""
from server.store.bootstrap import ensure_schema, ensure_demo_fixtures
from server.store import repositories as repo
from server.store.database import init_db
from server.tools import trip_tools
from server.domain import execution_service


def test_import_does_not_wipe_plans():
    ensure_schema()
    repo.seed_demo_data(wipe=True)
    execution_service.set_force_fail(None)
    import server.tools.trip_tools as tt
    tt._initialized = False

    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    plan_id = plan["plan_id"]

    # Simulate re-import / restart without wipe
    tt._initialized = False
    ensure_demo_fixtures(force=False)
    tt._initialized = True

    restored = repo.get_plan(plan_id)
    assert restored is not None
    assert restored["plan_hash"] == plan["plan_hash"]


def test_seed_without_wipe_preserves_preferences():
    ensure_schema()
    repo.seed_demo_data(wipe=True)
    trip_tools.save_preference("seat", "window")
    ensure_demo_fixtures(force=False)
    prefs = trip_tools.get_preferences()
    assert prefs["seat"]["value"] == "window"


def test_budget_rejection():
    ensure_schema()
    repo.seed_demo_data(wipe=True)
    # Lower budget below FLIGHT-A cost (2000)
    trip_tools.save_preference("max_additional_cost", 500)
    result = trip_tools.propose_rescue_plan("FLIGHT-A")
    assert result.get("ok") is False or "error" in result
    assert "exceeds" in str(result.get("error", "")).lower() or "budget" in str(result.get("error", "")).lower() or "cost" in str(result.get("error", "")).lower()


def test_budget_exact_boundary_allowed():
    """Cost equal to max should be allowed."""
    ensure_schema()
    repo.seed_demo_data(wipe=True)
    trip_tools.save_preference("max_additional_cost", 2000)  # FLIGHT-A cost
    result = trip_tools.propose_rescue_plan("FLIGHT-A")
    assert "plan_id" in result and "error" not in result
