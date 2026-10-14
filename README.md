# Trip Rescue AI

**One request. One coordinated recovery. You're always in control.**

Alexa+ Hackathon project — an AI agent that recovers disrupted trips across flights, hotels, rides and notifications with **explicit user approval** before any consequential action.

## Status: MVP Complete (Phases 0–9)

| Phase | Status | Summary |
|-------|--------|---------|
| 0 Scaffold | ✅ | Repo, docs, friction-log |
| 1 MCP foundation | ✅ | MCPServer (mcp 2.x), Streamable HTTP path, tools |
| 2 Data + mocks | ✅ | SQLite, 4h-delay scenario, providers |
| 3 Plan engine | ✅ | Versioned plans + SHA-256 hash |
| 4 Approval + execution | ✅ | Hash-bound approval, saga, rollback |
| 5 Memory + notifications | ✅ | Preferences, draft/send with approval |
| 6 Agent Skill + demo mode | ✅ | SKILL.md, deterministic orchestrator |
| 7 Deployment / QA | ✅ | Docker, health, CI, tests |
| 8 Demo polish | ✅ | Full UI journey, demo script |
| 9 Submission ready | ✅ | Checklist, product description, run scripts |

## Alexa+ demonstration path

This submission uses the **browser Recovery Cockpit simulator** as the primary demo client.
It calls the same domain tools registered on the MCP server via an HTTP facade.

- **Verified:** tool registration on MCPServer, domain approval/execution, HTTP E2E
- **Not claimed:** live Alexa device skill, official Alexa+ host runtime, real airline APIs

Judges should evaluate agent tool use, approval safety, and failure handling in the simulator.

## Data safety

- Schema init does **not** wipe data.
- Demo seed only inserts if missing; tests use explicit `wipe=True`.
- UI never claims success when the backend fails.

## Provider honesty

All flight, hotel, ride, and messaging operations use **local mock providers**.  
The UI and logs must never imply a real airline or hotel API was contacted.

## MCP note

The MCP server uses **MCP 2.x `MCPServer`** (FastMCP was renamed).  
The browser demo talks to the **HTTP tool facade** (`server/http_facade.py`) which calls the same domain functions the MCP tools use.

## Quick Start (Windows)

```powershell
# Terminal 1 – backend
.\run-backend.ps1

# Terminal 2 – frontend
.\run-frontend.ps1
```

Or manually:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn server.http_facade:app --reload --port 8000

# new terminal
cd simulator
npm install
npm run dev
```

Open **http://localhost:5173**

## Full demo journey

1. **Disruption** – 4h delay; connection / hotel / ride at risk  
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
- Notifications require hash-bound approval (not a client boolean)  
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

## Docs

- `docs/demo-script.md` – 2:45 judge demo  
- `docs/submission-checklist.md` – Phase 9 checklist  
- `docs/product-description.md` – submission form text  
- `docs/architecture.md` – system design  
- `docs/friction-log.md` – genuine platform friction  
- `skill/trip-rescue/SKILL.md` – agent skill  

## What is simulated

Mock flight / hotel / ride / message providers. No real airline bookings or payments.

## License

MIT
