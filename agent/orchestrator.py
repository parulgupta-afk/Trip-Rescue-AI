"""Agent orchestration entry – demo mode + optional live model hook."""
from __future__ import annotations

from server.tools import trip_tools
from agent.demo_model import DemoOrchestrator


def run_demo(selected_flight: str = "FLIGHT-A") -> list[dict]:
    """Run the full deterministic journey with real tools."""
    orch = DemoOrchestrator(trip_tools)
    return orch.run_happy_path(selected_flight)
