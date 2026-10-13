"""
Trip Rescue AI – MCP Server entrypoint.

Exposes tools via the official MCP Python SDK with Streamable HTTP transport.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from server.tools import trip_tools

mcp = FastMCP(
    "TripRescueAI",
    instructions=(
        "Trip Rescue AI coordinates recovery of disrupted trips. "
        "Always retrieve trip and status first, search alternatives, "
        "propose a complete plan, and NEVER execute without explicit approval."
    ),
)

# ---------- Register tools ----------

@mcp.tool()
def get_trip(trip_id: str = "TRIP-100") -> dict:
    """Retrieve the full itinerary including flight segments, hotel and ride bookings."""
    return trip_tools.get_trip(trip_id)


@mcp.tool()
def check_flight_status(trip_id: str = "TRIP-100") -> dict:
    """Check flight status and identify which parts of the itinerary are affected by a delay."""
    return trip_tools.check_flight_status(trip_id)


@mcp.tool()
def get_preferences(user_id: str = "user-alex") -> dict:
    """Retrieve the traveller's saved preferences (airline, seat, budget, overnight avoidance)."""
    return trip_tools.get_preferences(user_id)


@mcp.tool()
def search_alternatives(trip_id: str = "TRIP-100", user_id: str = "user-alex") -> dict:
    """Search and rank alternative flights against the traveller's preferences."""
    return trip_tools.search_alternatives(trip_id, user_id)


@mcp.tool()
def propose_rescue_plan(
    selected_flight_id: str,
    trip_id: str = "TRIP-100",
    user_id: str = "user-alex",
) -> dict:
    """
    Build a complete multi-service rescue plan (flight + hotel + ride + notification draft).
    Returns a versioned plan with a cryptographic hash. Does NOT execute any changes.
    """
    return trip_tools.propose_rescue_plan(selected_flight_id, trip_id, user_id)


@mcp.tool()
def save_preference(
    key: str,
    value: str | int | bool,
    user_id: str = "user-alex",
) -> dict:
    """Save a travel preference explicitly stated or confirmed by the user."""
    return trip_tools.save_preference(key, value, user_id)


# For local development: `python -m server.app` or uvicorn
if __name__ == "__main__":
    # Streamable HTTP is the default transport in recent FastMCP
    mcp.run(transport="streamable-http")
