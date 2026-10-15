"""Thin FastAPI facade for the React simulator — same domain as MCP tools."""
from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from server.tools import trip_tools

logger = logging.getLogger("trip_rescue.http")

app = FastAPI(title="Trip Rescue AI", version="0.7.0")

_origins = os.environ.get(
    "TRIP_RESCUE_CORS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Single-user demo identity — not production authentication
DEMO_USER = "user-alex"


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
    content_hash: str | None = None
    stale_after_seconds: int | None = None
    approved: bool | None = None  # deprecated, ignored for auth


def _error_http_status(error: str | None) -> int:
    err = error or ""
    if "not found" in err.lower() or err.endswith("_NOT_FOUND"):
        return 404
    mapping = {
        "UNKNOWN_TOOL": 404,
        "VALIDATION": 422,
        "PLAN_NOT_FOUND": 404,
        "TRIP_NOT_FOUND": 404,
        "NO_DRAFT": 404,
        "NO_SEND": 404,
        "NOT_APPROVED": 403,
        "NO_VALID_APPROVAL": 403,
        "OWNERSHIP": 403,
        "EXPIRED": 403,
        "HASH_MISMATCH": 409,
        "HASH_REQUIRED": 422,
        "INVALID_STATUS": 409,
        "INVALID_PLAN_STATUS": 409,
        "ALREADY_SENT": 409,
        "SEND_IN_PROGRESS": 409,
        "SEND_UNCERTAIN": 409,
        "SEND_STATE": 409,
        "CLAIM_FAILED": 409,
        "OWNERSHIP_LOST": 409,
        "EXECUTION_ACTIVE": 409,
        "CANNOT_ESTABLISH_STALENESS": 409,
        "INVALID_ARGUMENT": 422,
        "INTERNAL": 500,
    }
    return mapping.get(err, 400)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "TripRescueAI",
        "providers": "simulated",
        "auth": "single-user-demo",
        "version": "0.7.0",
    }


@app.post("/tools/{tool_name}")
def invoke_tool(tool_name: str, body: ToolArgs | None = None):
    body = body or ToolArgs()
    args = body.model_dump(exclude_none=True)

    # Validate stale_after_seconds if provided
    if "stale_after_seconds" in args and args["stale_after_seconds"] is not None:
        if not isinstance(args["stale_after_seconds"], int) or args["stale_after_seconds"] < 0:
            return JSONResponse(
                status_code=422,
                content={"ok": False, "error": "VALIDATION", "message": "stale_after_seconds must be a non-negative integer"},
            )
        if tool_name == "reconcile_stale_notification_send" and args["stale_after_seconds"] == 0:
            return JSONResponse(
                status_code=422,
                content={"ok": False, "error": "VALIDATION", "message": "stale_after_seconds must be greater than zero for notification reconciliation"},
            )

    # Ignore client-supplied user_id for authorization; demo identity is server-side
    user_id = DEMO_USER

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
        "save_preference": lambda: trip_tools.save_preference(args["key"], args["value"], user_id),
        "delete_preference": lambda: trip_tools.delete_preference(args["key"], user_id),
        "approve_rescue_plan": lambda: trip_tools.approve_rescue_plan(
            args["plan_id"], args["plan_hash"], user_id
        ),
        "execute_rescue_plan": lambda: trip_tools.execute_rescue_plan(
            args["plan_id"], user_id, args.get("force_fail_step"),
        ),
        "get_plan_status": lambda: trip_tools.get_plan_status(args["plan_id"], user_id),
        "recover_stuck_execution": lambda: trip_tools.recover_stuck_execution(
            args["plan_id"], user_id, args.get("stale_after_seconds") if args.get("stale_after_seconds") is not None else 120
        ),
        "draft_notifications": lambda: trip_tools.draft_notifications(args["plan_id"], user_id),
        "approve_notifications": lambda: trip_tools.approve_notifications(
            args["plan_id"], args["draft_hash"], user_id
        ),
        "send_notifications": lambda: trip_tools.send_notifications(
            args["plan_id"], args.get("draft_hash") or args.get("content_hash"), user_id
        ),
        "reconcile_stale_notification_send": lambda: trip_tools.reconcile_stale_notification_send(
            args["plan_id"],
            args.get("content_hash") or args.get("draft_hash"),
            user_id,
            args.get("stale_after_seconds") or 120,
        ),
    }

    if tool_name not in dispatch:
        return JSONResponse(
            status_code=404,
            content={"ok": False, "error": "UNKNOWN_TOOL", "message": f"Unknown tool: {tool_name}"},
        )

    required = {
        "propose_rescue_plan": ["selected_flight_id"],
        "approve_rescue_plan": ["plan_id", "plan_hash"],
        "execute_rescue_plan": ["plan_id"],
        "get_plan_status": ["plan_id"],
        "recover_stuck_execution": ["plan_id"],
        "draft_notifications": ["plan_id"],
        "approve_notifications": ["plan_id", "draft_hash"],
        "send_notifications": ["plan_id"],
        "reconcile_stale_notification_send": ["plan_id"],
        "save_preference": ["key", "value"],
        "delete_preference": ["key"],
    }
    for field in required.get(tool_name, []):
        if field not in args and not (
            field == "draft_hash" and (args.get("content_hash") or args.get("draft_hash"))
        ):
            if field == "draft_hash" and tool_name == "send_notifications":
                # send requires hash via draft_hash or content_hash
                if not args.get("draft_hash") and not args.get("content_hash"):
                    return JSONResponse(
                        status_code=422,
                        content={"ok": False, "error": "VALIDATION", "message": f"Missing required field: draft_hash"},
                    )
                continue
            if field not in args:
                return JSONResponse(
                    status_code=422,
                    content={"ok": False, "error": "VALIDATION", "message": f"Missing required field: {field}"},
                )

    if tool_name == "reconcile_stale_notification_send":
        if not args.get("content_hash") and not args.get("draft_hash"):
            return JSONResponse(
                status_code=422,
                content={"ok": False, "error": "VALIDATION", "message": "Missing required field: content_hash or draft_hash"},
            )

    try:
        result = dispatch[tool_name]()
    except KeyError as e:
        return JSONResponse(
            status_code=422,
            content={"ok": False, "error": "VALIDATION", "message": f"Missing field: {e}"},
        )
    except Exception:
        logger.exception("Tool %s failed", tool_name)
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": "INTERNAL", "message": "Tool execution failed"},
        )

    if isinstance(result, dict) and (result.get("ok") is False or (
        result.get("error") and not result.get("plan_id") and not result.get("alternatives")
        and not result.get("id") and not result.get("preferences") and result.get("status") is None
        and "steps" not in result
    )):
        err = result.get("error")
        # get_plan_status returns {error: ...} without ok
        if err:
            code = _error_http_status(err)
            body = result if result.get("ok") is False else {"ok": False, **result}
            return JSONResponse(status_code=code, content=body)

    if isinstance(result, dict) and result.get("ok") is False and result.get("error"):
        return JSONResponse(status_code=_error_http_status(result.get("error")), content=result)

    return result
