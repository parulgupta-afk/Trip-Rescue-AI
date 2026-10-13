"""Thin FastAPI facade for the React simulator."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any

from server.tools import trip_tools

app = FastAPI(title="Trip Rescue AI", version="0.5.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
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
    approved: bool | None = None


@app.get("/health")
def health():
    return {"status": "ok", "service": "TripRescueAI", "phase": "5-8"}


@app.post("/tools/{tool_name}")
def invoke_tool(tool_name: str, body: ToolArgs | None = None):
    body = body or ToolArgs()
    args = body.model_dump(exclude_none=True)

    dispatch = {
        "get_trip": lambda: trip_tools.get_trip(args.get("trip_id", "TRIP-100")),
        "check_flight_status": lambda: trip_tools.check_flight_status(args.get("trip_id", "TRIP-100")),
        "get_preferences": lambda: trip_tools.get_preferences(args.get("user_id", "user-alex")),
        "list_preferences": lambda: trip_tools.list_preferences(args.get("user_id", "user-alex")),
        "search_alternatives": lambda: trip_tools.search_alternatives(
            args.get("trip_id", "TRIP-100"), args.get("user_id", "user-alex")
        ),
        "propose_rescue_plan": lambda: trip_tools.propose_rescue_plan(
            args["selected_flight_id"],
            args.get("trip_id", "TRIP-100"),
            args.get("user_id", "user-alex"),
        ),
        "save_preference": lambda: trip_tools.save_preference(
            args["key"], args["value"], args.get("user_id", "user-alex")
        ),
        "approve_rescue_plan": lambda: trip_tools.approve_rescue_plan(
            args["plan_id"], args["plan_hash"], args.get("user_id", "user-alex")
        ),
        "execute_rescue_plan": lambda: trip_tools.execute_rescue_plan(
            args["plan_id"], args.get("user_id", "user-alex"), args.get("force_fail_step"),
        ),
        "get_plan_status": lambda: trip_tools.get_plan_status(args["plan_id"]),
        "draft_notifications": lambda: trip_tools.draft_notifications(
            args["plan_id"], args.get("user_id", "user-alex")
        ),
        "send_notifications": lambda: trip_tools.send_notifications(
            args["plan_id"], args.get("approved", False), args.get("user_id", "user-alex")
        ),
    }

    if tool_name not in dispatch:
        return {"error": f"Unknown tool: {tool_name}"}
    try:
        return dispatch[tool_name]()
    except Exception as e:
        return {"error": str(e)}
