# Trip Rescue AI

**One request. One coordinated recovery. You're always in control.**

Alexa+ Hackathon project — an AI agent that recovers disrupted trips across flights, hotels, rides and notifications with **explicit user approval** before any consequential action.

## MVP Status (Phases 0–8)

| Phase | Status | Summary |
|-------|--------|---------|
| 0 Scaffold | ✅ | Repo, docs, friction-log |
| 1 MCP foundation | ✅ | FastMCP server, Streamable HTTP, tools |
| 2 Data + mocks | ✅ | SQLite, 4h-delay scenario, providers |
| 3 Plan engine | ✅ | Versioned plans + SHA-256 hash |
| 4 Approval + execution | ✅ | Hash-bound approval, saga, rollback |
| 5 Memory + notifications | ✅ | Preferences, draft/send with approval |
| 6 Agent Skill + demo mode | ✅ | SKILL.md, deterministic orchestrator |
| 7 Deployment / QA | ✅ | Docker, health, CI, tests |
| 8 Demo polish | ✅ | Full UI journey, demo script |

## Quick Start (Windows)

```powershell
cd trip-rescue
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn server.http_facade:app --reload --port 8000

# new terminal
cd simulator
npm install
npm run dev
```

Open http://localhost:5173

## Full demo journey

1. **Disruption** – 4h delay, connection/hotel/ride at risk  
2. **Alternatives** – ranked by preference, cost, overnight  
3. **Rescue plan** – flight + hotel + ride + notification draft  
4. **Approve** – hash-bound; server rejects mismatch / no approval  
5. **Execute** – step results; optional forced failure + compensation  
6. **Notifications** – draft → separate send approval  
7. **Memory** – preferences persist and can be updated  

## Safety guarantees

- Plan generation ≠ execution  
- Approval bound to cryptographic plan hash  
- Stale / modified / expired approvals rejected  
- Idempotent execution  
- Compensating actions on partial failure  
- Notifications require their own approval  
- Server (not LLM) enforces authorization  

## Tools (MCP)

**Read:** `get_trip`, `check_flight_status`, `get_preferences`, `list_preferences`, `search_alternatives`, `get_plan_status`  
**Propose:** `propose_rescue_plan`, `draft_notifications`, `save_preference`  
**Commit:** `approve_rescue_plan`, `execute_rescue_plan`, `send_notifications`

## Deterministic demo mode

```python
from agent.orchestrator import run_demo
log = run_demo("FLIGHT-A")  # real tools, fixed sequence
```

## License

MIT
