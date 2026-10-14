"""Thin FastAPI facade for the React simulator — same domain as MCP tools."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Any
import os

from server.tools import trip_tools

app = FastAPI(title="Trip Rescue AI", version="0.6.0")

_origins = os.environ.get("TRIP_RESCUE_CORS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class ToolArgs(BaseModel):
    trip_id: str | None = None
    user_id: str | None = None
    selected_flight_id: str | None = None
    key: str | None = None
    value: Any = None
    plan_id: str | None = None
    plan_hash: str | None = None
    force_fail_step: str | None = None
    draft_hash: str | None = None
    # deprecated — not used for authorization
    approved: bool | None = None


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "TripRescueAI",
        "providers": "simulated",
        "version": "0.6.0",
    }


@app.post("/tools/{tool_name}")
def invoke_tool(tool_name: str, body: ToolArgs | None = None):
    body = body or ToolArgs()
    args = body.model_dump(exclude_none=True)

    # Demo identity — not authenticated; documented as single-user hackathon demo
    user_id = args.get("user_id", "user-alex")

    dispatch = {
        "get_trip": lambda: trip_tools.get_trip(args.get("trip_id", "TRIP-100")),
        "check_flight_status": lambda: trip_tools.check_flight_status(args.get("trip_id", "TRIP-100")),
        "get_preferences": lambda: trip_tools.get_preferences(user_id),
        "list_preferences": lambda: trip_tools.list_preferences(user_id),
        "search_alternatives": lambda: trip_tools.search_alternatives(
            args.get("trip_id", "TRIP-100"), user_id
        ),
        "propose_rescue_plan": lambda: trip_tools.propose_rescue_plan(
            args["selected_flight_id"],
            args.get("trip_id", "TRIP-100"),
            user_id,
        ),
        "save_preference": lambda: trip_tools.save_preference(
            args["key"], args["value"], user_id
        ),
        "delete_preference": lambda: trip_tools.delete_preference(args["key"], user_id),
        "approve_rescue_plan": lambda: trip_tools.approve_rescue_plan(
            args["plan_id"], args["plan_hash"], user_id
        ),
        "execute_rescue_plan": lambda: trip_tools.execute_rescue_plan(
            args["plan_id"], user_id, args.get("force_fail_step"),
        ),
        "get_plan_status": lambda: trip_tools.get_plan_status(args["plan_id"]),
        "draft_notifications": lambda: trip_tools.draft_notifications(
            args["plan_id"], user_id
        ),
        "approve_notifications": lambda: trip_tools.approve_notifications(
            args["plan_id"], args["draft_hash"], user_id
        ),
        "send_notifications": lambda: trip_tools.send_notifications(
            args["plan_id"], args.get("draft_hash"), user_id
        ),
    }

    if tool_name not in dispatch:
        raise HTTPException(status_code=404, detail={"error": "UNKNOWN_TOOL", "message": f"Unknown tool: {tool_name}"})

    required = {
        "propose_rescue_plan": ["selected_flight_id"],
        "approve_rescue_plan": ["plan_id", "plan_hash"],
        "execute_rescue_plan": ["plan_id"],
        "get_plan_status": ["plan_id"],
        "draft_notifications": ["plan_id"],
        "approve_notifications": ["plan_id", "draft_hash"],
        "send_notifications": ["plan_id"],
        "save_preference": ["key", "value"],
        "delete_preference": ["key"],
    }
    for field in required.get(tool_name, []):
        if field not in args:
            raise HTTPException(
                status_code=422,
                detail={"error": "VALIDATION", "message": f"Missing required field: {field}"},
            )

    try:
        result = dispatch[tool_name]()
    except KeyError as e:
        raise HTTPException(status_code=422, detail={"error": "VALIDATION", "message": f"Missing field: {e}"})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": "INTERNAL", "message": "Tool execution failed"})

    if isinstance(result, dict) and result.get("error") and result.get("ok") is False:
        code = 400
        if result.get("error") in ("NOT_APPROVED", "NO_VALID_APPROVAL", "OWNERSHIP", "EXPIRED"):
            code = 403
        if result.get("error") == "PLAN_NOT_FOUND":
            code = 404
        # Still return body for client; status reflects error class
        return result
    return result
