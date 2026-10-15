
"""HTTP status code tests for the FastAPI facade."""
from fastapi.testclient import TestClient
from server.store.bootstrap import ensure_schema
from server.store import repositories as repo
from server.domain import execution_service
from server.http_facade import app
from server.tools import trip_tools
import server.tools.trip_tools as tt


def setup_function():
    ensure_schema()
    repo.seed_demo_data(wipe=True)
    execution_service.set_force_fail(None)
    tt._initialized = True


client = TestClient(app)


def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_unknown_tool_404():
    r = client.post("/tools/not_a_real_tool", json={})
    assert r.status_code == 404
    assert r.json()["error"] == "UNKNOWN_TOOL"


def test_missing_param_422():
    r = client.post("/tools/propose_rescue_plan", json={})
    assert r.status_code == 422


def test_get_trip_200():
    r = client.post("/tools/get_trip", json={})
    assert r.status_code == 200
    assert r.json().get("id") == "TRIP-100"


def test_execute_without_approval_forbidden():
    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    r = client.post("/tools/execute_rescue_plan", json={"plan_id": plan["plan_id"]})
    assert r.status_code in (403, 400)
    body = r.json()
    assert body.get("ok") is False


def test_plan_status_ok_for_owner():
    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    r = client.post("/tools/get_plan_status", json={"plan_id": plan["plan_id"]})
    assert r.status_code == 200
    assert r.json().get("plan_id") == plan["plan_id"]


def test_reconcile_missing_content_hash_422():
    r = client.post("/tools/reconcile_stale_notification_send", json={"plan_id": "PLAN-1"})
    assert r.status_code == 422
    assert r.json().get("error") == "VALIDATION"


def test_reconcile_negative_or_zero_or_short_stale_seconds_422():
    r_neg = client.post("/tools/reconcile_stale_notification_send", json={"plan_id": "PLAN-1", "content_hash": "abc", "stale_after_seconds": -5})
    assert r_neg.status_code == 422
    assert r_neg.json().get("error") == "VALIDATION"

    r_zero = client.post("/tools/reconcile_stale_notification_send", json={"plan_id": "PLAN-1", "content_hash": "abc", "stale_after_seconds": 0})
    assert r_zero.status_code == 422
    assert r_zero.json().get("error") == "VALIDATION"

    r_short = client.post("/tools/reconcile_stale_notification_send", json={"plan_id": "PLAN-1", "content_hash": "abc", "stale_after_seconds": 5})
    assert r_short.status_code == 422
    assert r_short.json().get("error") == "VALIDATION"


def test_recover_negative_zero_or_short_stale_seconds_422():
    r_neg = client.post("/tools/recover_stuck_execution", json={"plan_id": "PLAN-1", "stale_after_seconds": -1})
    assert r_neg.status_code == 422
    assert r_neg.json().get("error") == "VALIDATION"

    r_zero = client.post("/tools/recover_stuck_execution", json={"plan_id": "PLAN-1", "stale_after_seconds": 0})
    assert r_zero.status_code == 422
    assert r_zero.json().get("error") == "VALIDATION"

    r_short = client.post("/tools/recover_stuck_execution", json={"plan_id": "PLAN-1", "stale_after_seconds": 5})
    assert r_short.status_code == 422
    assert r_short.json().get("error") == "VALIDATION"


def test_missing_trip_returns_404():
    r = client.post("/tools/get_trip", json={"trip_id": "TRIP-NONEXISTENT"})
    assert r.status_code == 404
    assert r.json().get("error") == "TRIP_NOT_FOUND"


def test_missing_plan_returns_404():
    r = client.post("/tools/get_plan_status", json={"plan_id": "PLAN-NONEXISTENT"})
    assert r.status_code == 404
    assert r.json().get("error") == "PLAN_NOT_FOUND"


def test_client_supplied_user_id_cannot_bypass_demo_user():
    # Attempting to query with a fake user_id still evaluates with DEMO_USER
    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    r = client.post(
        "/tools/get_plan_status",
        json={"plan_id": plan["plan_id"], "user_id": "malicious-user"},
    )
    # The server overrides user_id with DEMO_USER ('user-alex')
    assert r.status_code == 200
    assert r.json().get("plan_id") == plan["plan_id"]


