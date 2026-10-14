"""MCP protocol validation tests (MCPServer and Streamable HTTP)."""
import pytest
from server.app import mcp
from server.store.bootstrap import ensure_schema
from server.store import repositories as repo


@pytest.fixture(autouse=True)
def setup_data():
    ensure_schema()
    repo.seed_demo_data(wipe=True)


async def test_mcp_tool_discovery():
    """Verify tool discovery exposes domain tools through MCPServer."""
    tools = await mcp.list_tools()
    assert len(tools) >= 10
    names = [t.name for t in tools]
    assert "get_trip" in names
    assert "check_flight_status" in names
    assert "propose_rescue_plan" in names
    assert "approve_rescue_plan" in names
    assert "execute_rescue_plan" in names
    assert "send_notifications" in names


async def test_mcp_safe_tool_invocation():
    """Verify safe read tool invocation over MCP protocol."""
    res = await mcp.call_tool("check_flight_status", {"trip_id": "TRIP-100"})
    assert res.is_error is False
    assert len(res.content) >= 1
    assert "disrupted" in res.content[0].text
    assert "EX-401" in res.content[0].text


def test_mcp_streamable_http_routes():
    """Verify streamable HTTP starlette app is properly configured."""
    app = mcp.streamable_http_app()
    route_paths = [r.path for r in getattr(app, "routes", [])]
    assert "/mcp" in route_paths
