"""Trip Rescue AI – MCP Server (MCP 2.x MCPServer)."""
from __future__ import annotations

from mcp.server.mcpserver import MCPServer
from server.tools import trip_tools

mcp = MCPServer(
    "TripRescueAI",
    instructions=(
        "Trip Rescue AI coordinates recovery of disrupted trips. "
        "Always retrieve trip and status first, search alternatives, "
        "propose a complete plan, and NEVER execute without explicit approval. "
        "Notifications require hash-bound approve_notifications before send."
    ),
)


@mcp.tool()
def get_trip(trip_id: str = "TRIP-100") -> dict:
    """Retrieve the full itinerary including flight segments, hotel and ride bookings."""
    return trip_tools.get_trip(trip_id)


@mcp.tool()
def check_flight_status(trip_id: str = "TRIP-100") -> dict:
    """Check flight status and identify affected itinerary items."""
    return trip_tools.check_flight_status(trip_id)


@mcp.tool()
def get_preferences(user_id: str = "user-alex") -> dict:
    """Retrieve saved travel preferences."""
    return trip_tools.get_preferences(user_id)


@mcp.tool()
def list_preferences(user_id: str = "user-alex") -> dict:
    """List all saved preferences."""
    return trip_tools.list_preferences(user_id)


@mcp.tool()
def search_alternatives(trip_id: str = "TRIP-100", user_id: str = "user-alex") -> dict:
    """Search and rank alternative flights against preferences."""
    return trip_tools.search_alternatives(trip_id, user_id)


@mcp.tool()
def propose_rescue_plan(
    selected_flight_id: str,
    trip_id: str = "TRIP-100",
    user_id: str = "user-alex",
) -> dict:
    """Build a multi-service rescue plan. Does NOT execute. Rejects over-budget plans."""
    return trip_tools.propose_rescue_plan(selected_flight_id, trip_id, user_id)


@mcp.tool()
def save_preference(key: str, value: str | int | bool, user_id: str = "user-alex") -> dict:
    """Save a travel preference."""
    return trip_tools.save_preference(key, value, user_id)


@mcp.tool()
def delete_preference(key: str, user_id: str = "user-alex") -> dict:
    """Delete a saved preference."""
    return trip_tools.delete_preference(key, user_id)


@mcp.tool()
def approve_rescue_plan(plan_id: str, plan_hash: str, user_id: str = "user-alex") -> dict:
    """Record hash-bound approval of the exact plan."""
    return trip_tools.approve_rescue_plan(plan_id, plan_hash, user_id)


@mcp.tool()
def execute_rescue_plan(
    plan_id: str,
    user_id: str = "user-alex",
    force_fail_step: str | None = None,
) -> dict:
    """Execute an approved plan. Optional force_fail_step for compensation demo."""
    return trip_tools.execute_rescue_plan(plan_id, user_id, force_fail_step)


@mcp.tool()
def get_plan_status(plan_id: str) -> dict:
    """Retrieve execution progress and results."""
    return trip_tools.get_plan_status(plan_id)


@mcp.tool()
def draft_notifications(plan_id: str, user_id: str = "user-alex") -> dict:
    """Draft and persist notification messages with content hash."""
    return trip_tools.draft_notifications(plan_id, user_id)


@mcp.tool()
def approve_notifications(plan_id: str, draft_hash: str, user_id: str = "user-alex") -> dict:
    """Approve exact notification draft (hash-bound)."""
    return trip_tools.approve_notifications(plan_id, draft_hash, user_id)


@mcp.tool()
def send_notifications(
    plan_id: str,
    draft_hash: str | None = None,
    user_id: str = "user-alex",
) -> dict:
    """Send notifications only with valid hash-bound approval."""
    return trip_tools.send_notifications(plan_id, draft_hash, user_id)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
