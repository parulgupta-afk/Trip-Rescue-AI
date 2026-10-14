"""Basic tool tests – run with pytest."""
from server.tools import trip_tools
from server.store.bootstrap import ensure_schema
from server.store.database import init_db
from server.store import repositories as repo


def setup_module():
    ensure_schema()
    repo.seed_demo_data(wipe=True)


def test_get_trip():
    trip = trip_tools.get_trip("TRIP-100")
    assert trip["id"] == "TRIP-100"
    assert len(trip["segments"]) == 2
    assert any(b["kind"] == "hotel" for b in trip["bookings"])


def test_check_flight_status():
    status = trip_tools.check_flight_status("TRIP-100")
    assert status["disrupted"] is True
    assert status["delay_hours"] == 4
    assert len(status["affected"]) == 3


def test_search_alternatives():
    result = trip_tools.search_alternatives()
    assert result["count"] == 3
    assert result["alternatives"][0]["rank"] == 1


def test_propose_rescue_plan():
    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    assert "plan_id" in plan
    assert plan["total_cost_delta"] == 2000
    assert plan["plan_hash"]
    assert any(a["type"] == "change_flight" for a in plan["actions"])
    assert any(a["type"] == "reschedule_hotel" for a in plan["actions"])
    assert any(a["type"] == "reschedule_ride" for a in plan["actions"])


def test_preferences():
    prefs = trip_tools.get_preferences()
    assert "preferred_airline" in prefs
    trip_tools.save_preference("seat", "window")
    updated = trip_tools.get_preferences()
    assert updated["seat"]["value"] == "window"
