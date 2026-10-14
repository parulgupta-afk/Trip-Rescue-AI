"""Smoke-test MCP server import and tool listing (not the HTTP facade)."""
from __future__ import annotations
import asyncio
import sys


async def main() -> int:
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
    print("NOTE: Streamable HTTP network client not exercised in this script.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
