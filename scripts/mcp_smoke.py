"""MCP smoke: registration + optional Streamable HTTP network check.

Usage:
  PYTHONPATH=. python scripts/mcp_smoke.py           # registration only
  PYTHONPATH=. python scripts/mcp_smoke.py --network # start server + client over HTTP
"""
from __future__ import annotations

import argparse
import asyncio
import socket
import sys
import threading
import time


async def registration_check() -> int:
    try:
        from server.app import mcp
    except Exception as e:
        print("FAIL: cannot import MCP server:", e)
        return 1
    print("OK: MCP server name =", getattr(mcp, "name", "?"))
    try:
        tools = await mcp.list_tools()
        names = [getattr(t, "name", str(t)) for t in tools]
        print("OK: tools =", names)
        if "get_trip" not in names:
            print("FAIL: get_trip not registered")
            return 1
    except Exception as e:
        print("FAIL: list_tools:", e)
        return 1
    return 0


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


async def network_check() -> int:
    import uvicorn
    from mcp import Client
    from server.app import mcp

    port = _free_port()
    app = mcp.streamable_http_app()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", lifespan="on")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.05)
    else:
        print("FAIL: server did not start")
        return 1

    url = f"http://127.0.0.1:{port}/mcp"
    print("OK: Streamable HTTP listening at", url)
    try:
        async with Client(url) as client:
            tools = await client.list_tools()
            tool_list = getattr(tools, "tools", tools)
            names = [t.name for t in tool_list]
            print("OK: network list_tools =", names)
            if "check_flight_status" not in names:
                print("FAIL: check_flight_status missing")
                return 1
            result = await client.call_tool("check_flight_status", {"trip_id": "TRIP-100"})
            print("OK: network call_tool result type =", type(result).__name__)
            if getattr(result, "is_error", False):
                print("FAIL: tool error", result)
                return 1
    except Exception as e:
        print("FAIL: network client:", e)
        return 1
    finally:
        server.should_exit = True
        thread.join(timeout=10)
    print("OK: Streamable HTTP network smoke passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--network", action="store_true", help="Run real Streamable HTTP client/server test")
    args = parser.parse_args()
    code = asyncio.run(registration_check())
    if code != 0:
        return code
    if args.network:
        return asyncio.run(network_check())
    print("NOTE: pass --network for Streamable HTTP client/server smoke.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
