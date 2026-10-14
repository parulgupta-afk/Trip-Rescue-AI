"""
Real MCP Streamable-HTTP network test.

Starts the Starlette /mcp app on an ephemeral port using uvicorn in a
background thread, then connects with a genuine MCP ClientSession over
the HTTP transport.  Validates:
  1. Tool list contains all 14 expected tools.
  2. A safe read-only tool (check_flight_status) returns a valid response.

This script does NOT exercise the FastAPI /tools REST facade -- it uses
the real MCP protocol transport so transport-layer bugs are caught here.
"""
from __future__ import annotations

import asyncio
import socket
import sys
import threading
import time

import uvicorn


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_server(port: int) -> threading.Event:
    """Run the MCP Starlette app in a daemon thread; return a ready event."""
    from server.app import mcp
    from server.store.bootstrap import ensure_schema, ensure_demo_fixtures

    ensure_schema()
    ensure_demo_fixtures(force=False)

    starlette_app = mcp.streamable_http_app()
    config = uvicorn.Config(
        starlette_app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        loop="asyncio",
    )
    server = uvicorn.Server(config)
    ready = threading.Event()

    def _run() -> None:
        original_startup = server.startup

        async def _patched_startup(*args, **kwargs):
            await original_startup(*args, **kwargs)
            ready.set()

        server.startup = _patched_startup
        asyncio.run(server.serve())

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return ready


EXPECTED_TOOLS = {
    "get_trip", "check_flight_status", "get_preferences", "list_preferences",
    "search_alternatives", "propose_rescue_plan", "save_preference",
    "delete_preference", "approve_rescue_plan", "execute_rescue_plan",
    "get_plan_status", "draft_notifications", "approve_notifications",
    "send_notifications",
}


async def run_test(port: int) -> int:
    from mcp.client.streamable_http import streamable_http_client
    from mcp import ClientSession

    url = f"http://127.0.0.1:{port}/mcp"
    print(f"Connecting to MCP server at {url} ...")

    async with streamable_http_client(url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            result = await session.list_tools()
            names = {t.name for t in result.tools}
            print(f"OK: discovered {len(names)} tools")
            missing = EXPECTED_TOOLS - names
            if missing:
                print(f"FAIL: missing tools: {missing}")
                return 1

            call_result = await session.call_tool(
                "check_flight_status", {"trip_id": "TRIP-100"}
            )
            if call_result.is_error:
                print(f"FAIL: check_flight_status error: {call_result}")
                return 1
            content_text = call_result.content[0].text if call_result.content else ""
            if "disrupted" not in content_text:
                print(f"FAIL: unexpected response: {content_text[:200]}")
                return 1
            print(f"OK: check_flight_status responded correctly")

    print("PASS: MCP Streamable HTTP transport test succeeded.")
    return 0


def main() -> int:
    port = _free_port()
    print(f"Starting MCP server on ephemeral port {port} ...")
    ready = _start_server(port)
    if not ready.wait(timeout=15):
        print("FAIL: server did not become ready within 15s")
        return 1
    time.sleep(0.3)
    return asyncio.run(run_test(port))


if __name__ == "__main__":
    sys.exit(main())
