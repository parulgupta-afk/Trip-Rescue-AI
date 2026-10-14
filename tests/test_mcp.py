"""MCP protocol validation — in-process discovery + real Streamable HTTP network."""
from __future__ import annotations

import socket
import threading
import time

import pytest
import uvicorn

from server.app import mcp
from server.store.bootstrap import ensure_schema
from server.store import repositories as repo


@pytest.fixture(autouse=True)
def setup_data():
    ensure_schema()
    repo.seed_demo_data(wipe=True)


async def test_mcp_tool_discovery():
    """Verify tool discovery exposes domain tools through MCPServer (in-process)."""
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
    """Verify safe read tool invocation over MCP protocol (in-process)."""
    res = await mcp.call_tool("check_flight_status", {"trip_id": "TRIP-100"})
    assert res.is_error is False
    assert len(res.content) >= 1
    assert "disrupted" in res.content[0].text
    assert "EX-401" in res.content[0].text


def test_mcp_streamable_http_routes():
    """Verify streamable HTTP Starlette app exposes /mcp."""
    app = mcp.streamable_http_app()
    route_paths = [r.path for r in getattr(app, "routes", [])]
    assert "/mcp" in route_paths


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture
def mcp_http_server():
    """Start the real MCP Streamable HTTP app on a local port."""
    port = _free_port()
    app = mcp.streamable_http_app()
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        lifespan="on",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait until the port accepts connections
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.05)
    else:
        server.should_exit = True
        thread.join(timeout=5)
        pytest.fail("MCP Streamable HTTP server did not start")

    yield f"http://127.0.0.1:{port}/mcp"

    server.should_exit = True
    thread.join(timeout=10)


@pytest.mark.asyncio
async def test_mcp_streamable_http_network_list_and_call(mcp_http_server):
    """
    Real network test: MCP client connects over Streamable HTTP,
    initializes a session, lists tools, and invokes a read-only tool.

    This is NOT the FastAPI /tools/{name} facade.
    """
    from mcp import Client

    url = mcp_http_server
    async with Client(url) as client:
        tools = await client.list_tools()
        # Client.list_tools may return ListToolsResult or list depending on version
        tool_list = getattr(tools, "tools", tools)
        names = [t.name for t in tool_list]
        assert "get_trip" in names, f"get_trip missing from {names}"
        assert "check_flight_status" in names

        result = await client.call_tool("check_flight_status", {"trip_id": "TRIP-100"})
        # Normalize CallToolResult
        is_error = getattr(result, "is_error", None)
        if is_error is True:
            pytest.fail(f"check_flight_status returned error: {result}")
        content = getattr(result, "content", None) or []
        text_parts = []
        for block in content:
            text_parts.append(getattr(block, "text", str(block)))
        combined = " ".join(text_parts)
        assert "disrupted" in combined.lower() or "EX-401" in combined or "true" in combined.lower(), (
            f"unexpected tool payload: {combined[:500]}"
        )
