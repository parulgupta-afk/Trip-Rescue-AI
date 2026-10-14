"""
Deterministic demo orchestrator.
Uses REAL MCP tools / application state – never prerecorded results.
Controls conversation flow only so the demo is repeatable without a live LLM.
"""
from __future__ import annotations

from typing import Any, Callable


class DemoOrchestrator:
    """Step-through the full recovery journey using real tool functions."""

    def __init__(self, tools: Any):
        self.tools = tools
        self.state: dict[str, Any] = {}

    def run_happy_path(self, selected_flight: str = "FLIGHT-A") -> list[dict]:
        log: list[dict] = []

        def step(name: str, fn: Callable, **kwargs):
            result = fn(**kwargs) if kwargs else fn()
            log.append({"tool": name, "result_summary": _summary(result)})
            self.state[name] = result
            return result

        step("get_trip", self.tools.get_trip)
        step("check_flight_status", self.tools.check_flight_status)
        step("get_preferences", self.tools.get_preferences)
        step("search_alternatives", self.tools.search_alternatives)
        plan = step("propose_rescue_plan", self.tools.propose_rescue_plan, selected_flight_id=selected_flight)
        step("approve_rescue_plan", self.tools.approve_rescue_plan,
             plan_id=plan["plan_id"], plan_hash=plan["plan_hash"])
        step("execute_rescue_plan", self.tools.execute_rescue_plan, plan_id=plan["plan_id"])
        draft = step("draft_notifications", self.tools.draft_notifications, plan_id=plan["plan_id"])
        step("approve_notifications", self.tools.approve_notifications,
             plan_id=plan["plan_id"], draft_hash=draft["content_hash"])
        step("send_notifications", self.tools.send_notifications,
             plan_id=plan["plan_id"], draft_hash=draft["content_hash"])
        step("list_preferences", self.tools.list_preferences)
        return log


def _summary(obj: Any) -> str:
    if not isinstance(obj, dict):
        return str(obj)[:80]
    if "error" in obj:
        return f"error={obj['error']}"
    if "status" in obj:
        return f"status={obj['status']}"
    if "plan_id" in obj:
        return f"plan={obj['plan_id']}"
    if "disrupted" in obj:
        return f"disrupted={obj['disrupted']}"
    if "alternatives" in obj:
        return f"alts={obj.get('count', len(obj['alternatives']))}"
    if "preferences" in obj:
        return f"prefs={obj.get('count', len(obj['preferences']))}"
    if "sent" in obj:
        return f"sent={len(obj['sent'])}"
    return "ok"
