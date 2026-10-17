# Trip Rescue AI

**One request. One coordinated recovery. You're always in control.**

An AI agent system that autonomously coordinates recovery across flights, hotels, ground transportation, and notifications when travel disruptions occur — built on **Model Context Protocol (MCP)** with **strict cryptographic approval boundaries** and **distributed saga execution safety**.

---

## The Problem Being Solved

When a flight is delayed or cancelled, travelers face cascading failures: missed connections, hotel check-in penalties, stranded ground transportation, and anxious contacts. Existing AI assistants either hallucinate bookings or execute irreversible real-world side effects without durable consent.

**Trip Rescue AI** solves this with an architectural guarantee:
- **Proposal is separate from execution**: An agent can research, search alternatives, and synthesize a multi-leg rescue plan, but it has zero authority to commit funds or send messages.
- **Cryptographic Hash-Bound Approvals**: Approvals are bound to a SHA-256 hash of the exact proposed plan and notification content. Any discrepancy, expiry, or tampering rejects execution.
- **Distributed Saga & Idempotent Workers**: Multi-step actions (flight booking, hotel rebooking, ride adjustment) execute atomically under durable SQLite leases with automated compensation on failure.

---

## Architectural Overview

```
                      +---------------------------------------+
                      |   Browser Recovery Cockpit (React)   |
                      +---------------------------------------+
                                  |                 |
                HTTP Tool Facade  |                 | MCP Streamable HTTP
              (/tools/{tool_name})|                 | (/mcp)
                                  v                 v
                      +---------------------------------------+
                      |       FastAPI / MCP Server (2.x)      |
                      +---------------------------------------+
                                          |
                      +-------------------+-------------------+
                      |                                       |
                      v                                       v
         +-------------------------+             +-------------------------+
         |    Execution Service    |             |  Notification Service   |
         |  - Saga coordinator     |             |  - Hash-bound approval  |
         |  - Atomic DB leases     |             |  - Continuous heartbeat |
         |  - Step compensation    |             |  - Stale reconciliation |
         +-------------------------+             +-------------------------+
                      |                                       |
                      +-------------------+-------------------+
                                          |
                                          v
                      +---------------------------------------+
                      |     Durable SQLite (WAL Mode)         |
                      |  - Plans, Steps, Approvals, Sends     |
                      +---------------------------------------+
                                          |
                                          v
                      +---------------------------------------+
                      |        Simulated Mock Providers       |
                      |  - Flight, Hotel, Ride, Messaging     |
                      +---------------------------------------+
```

### Core Invariants

1. **Only one worker executes a plan**: Claimed via atomic conditional SQL (`UPDATE plans SET status='executing' WHERE status='approved'`).
2. **Cryptographic hash verification**: Execution demands an unexpired, unconsumed approval record whose `plan_hash` exactly matches `sha256(canonical(plan))`.
3. **Continuous lease heartbeats**: Background heartbeat workers renew execution and notification leases. If a worker crashes, the lease expires safely.
4. **No blind redispatch on uncertainty**: Ambiguous provider timeouts or partial deliveries transition to `uncertain` state and refuse automated re-execution.
5. **Server-enforced thresholds**: Recovery operations enforce `MIN_RECOVERY_STALE_SECONDS = 30` to prevent caller-forced preemption of active workers.

---

## Verified vs. Simulated Disclosures

In accordance with strict hackathon honesty and engineering rigor:

| Component / Layer | Status | Implementation Details |
| :--- | :--- | :--- |
| **Approval-Bound Saga Engine** | **Verified** | Production-ready Python domain services with full ACID transaction boundaries. |
| **MCP Streamable HTTP Server** | **Verified** | MCP 2.x `MCPServer` exposing 16 tools via Streamable HTTP transport (`/mcp`). |
| **HTTP Tool Facade** | **Verified** | FastAPI gateway matching tool contracts for REST/Web clients (`/tools/*`). |
| **Browser Simulator UI** | **Verified** | React 19 + TypeScript + Vite cockpit with live backend synchronization. |
| **Database Migrations & Seed** | **Verified** | Non-destructive schema evolution; idempotent demo user `user-alex`. |
| **Travel Providers (Air/Hotel/Ride)**| **Simulated**| Local deterministic mock providers with configurable failure hooks. |
| **SMS/Message Dispatch** | **Simulated**| In-memory message dispatcher recording delivery attempts and payloads. |
| **Alexa+ Device / Skill Host** | **Simulated**| No live hardware skill claimed; agent interacts via MCP tools and simulator. |

---

## Technology Stack

- **Backend**: Python 3.12+ (tested on Python 3.12–3.14)
- **Frameworks**: FastAPI, Uvicorn, Model Context Protocol Python SDK (`mcp` 2.x), Pydantic
- **Database**: SQLite with Write-Ahead Logging (WAL) and foreign key constraints
- **Frontend**: React 19, TypeScript, Vite 6, TailwindCSS / Vanilla CSS
- **Testing**: Pytest, AsyncIO, Pytest-AsyncIO, Requests, AnyIO

---

## MCP Tools Reference

The MCP Server (`ServerName: TripRescueAI`) registers 16 tools:

| Tool | Category | Description |
| :--- | :--- | :--- |
| `get_trip` | Read | Retrieve trip legs, status, passengers, and disruption alerts. |
| `check_flight_status` | Read | Check real-time status, delays, and gate changes for a flight. |
| `get_preferences` | Read | Retrieve traveler constraints (budget, airline, cabin, seats). |
| `list_preferences` | Read | List all saved traveler preferences. |
| `search_alternatives` | Read | Query available alternative flights and routing options. |
| `propose_rescue_plan` | Propose | Generate a multi-step recovery plan with deterministic SHA-256 hash. |
| `approve_rescue_plan` | Commit | Authorize execution by recording cryptographic approval for the plan hash. |
| `execute_rescue_plan` | Commit | Atomically claim, lease, and execute recovery steps with rollback. |
| `get_plan_status` | Read | Query plan state, step logs, worker leases, and error details. |
| `save_preference` | Memory | Save or update durable user preference keys and values. |
| `delete_preference` | Memory | Remove a user preference entry. |
| `draft_notifications` | Propose | Draft contextual stakeholder updates with canonical content hash. |
| `approve_notifications`| Commit | Record explicit approval for the exact notification content hash. |
| `send_notifications` | Commit | Dispatch approved notifications with continuous lease heartbeat. |
| `recover_stuck_execution` | Recover | Safely reclaim abandoned execution after server lease expiry. |
| `reconcile_stale_notification_send` | Recover | Safely resolve stalled notification dispatches without re-dispatch. |

---

## Setup and Installation

### Prerequisites
- Python 3.12+
- Node.js 20+ and npm
- Git

### 1. Backend Setup

```bash
# Clone repository
git clone https://github.com/parulgupta-afk/Trip-Rescue-AI.git
cd "Trip Rescue AI"

# Create and activate virtual environment
python -m venv .venv

# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
# source .venv/bin/activate

# Install package with development dependencies
pip install -e ".[dev]"
```

### 2. Frontend Simulator Setup

```bash
cd simulator
npm install
cd ..
```
# Terminal 2: Launch Frontend Simulator
.\run-frontend.ps1


# Terminal 3: Launch Backend Simulator
.\run-backend.ps1
---

## Configuration & Environment Variables

| Variable | Scope | Default | Description |
| :--- | :--- | :--- | :--- |
| `DATABASE_PATH` | Backend | `trip_rescue.db` | Path to SQLite database file. |
| `VITE_MCP_URL` | Frontend | `http://localhost:8000` | Backend API base URL (trailing slashes auto-stripped). |
| `PORT` | Backend | `8000` | HTTP Facade and MCP server port. |

---

## Running the Application

### Option A: Using Helper Scripts (Windows PowerShell)

```powershell
# Terminal 1: Launch Backend (FastAPI + MCP)
cd simulator
npm run dev

# Terminal 2: Launch Frontend Simulator
.\run-frontend.ps1
```

# Terminal 3: Launch Backend Simulator
.\run-backend.ps1


### Option B: Manual Launch

```bash
# Terminal 1: Backend
uvicorn server.http_facade:app --reload --port 8000

# Terminal 2: Frontend
cd simulator
npm run dev
```

Open **http://localhost:5173** in your browser.

---

## Automated Test Suite

Run the full automated test suite verifying execution safety, approvals, notifications, MCP transport, and seed idempotency:

```bash
# Run all unit and integration tests (71 tests)
pytest tests/ -v

# Run MCP tool registration smoke test
python scripts/mcp_smoke.py

# Run MCP Streamable HTTP network client/server smoke test
python scripts/mcp_smoke.py --network

# Frontend type check & production build
cd simulator
npx tsc --noEmit
npm run build
```

---

## Demonstration Scenarios (Scenarios A – G)

### Scenario A: Successful End-to-End Recovery
1. Open the Cockpit at `http://localhost:5173`.
2. Flight `DL456` experiences a 4-hour delay, placing connecting flight and hotel check-in at risk.
3. Click **Propose Rescue Plan**. The server builds a plan and calculates cost differentials.
4. Click **Approve Plan (Bind SHA-256 Hash)**. The UI locks to the exact plan hash.
5. Click **Execute Rescue Plan**. The saga books the alternative flight, updates the hotel, adjusts the ride, and transitions to `succeeded`.
6. Click **Draft Notifications** -> **Approve Notifications** -> **Send Notifications**. All stakeholders are updated.

### Scenario B: Approval Required Before Side Effects
- Attempting to call `/tools/execute_rescue_plan` without prior approval returns HTTP 403 `APPROVAL_REQUIRED`. No provider side effects occur.

### Scenario C: Provider Failure & Saga Compensation
- Triggering a failure in step 2 (hotel rebooking) triggers compensating actions (e.g. cancelling the booked flight) and marks the plan `partial_failure`.

### Scenario D: Network Timeout & Ambiguous Outcomes
- When a timeout occurs during execution, the plan enters `uncertain`. The UI displays a warning banner and allows the user to query server status without blindly retrying.

### Scenario E: Duplicate & Concurrent Requests
- Concurrent execution requests race on atomic SQLite claims. Exactly one worker claims the plan; the other is rejected or receives an idempotent view. Provider steps run exactly once.

### Scenario F: Notification Uncertainty
- If a message provider fails or disconnects during dispatch, sent messages are retained as partial results, status becomes `uncertain`, and automated redispatch is blocked to prevent spamming.

### Scenario G: Stale Execution Recovery
- If a worker crashes mid-execution, `recover_stuck_execution` safely reclaims the plan after the 30-second server lease expires, refusing to interrupt active healthy workers.

---

## Known Limitations

1. **Simulated Providers**: Real-world airline GDS/NDC protocols and live payment gateways are simulated via local deterministic providers.
2. **Single-User Demo Authentication**: Uses a demo identity (`user-alex`). Production deployment requires multi-tenant JWT/OAuth2 session tokens.
3. **No Direct Alexa Runtime**: The project integrates via MCP tools and the web cockpit simulator; no native Alexa hardware voice model is bundled.

---

## License

MIT License. See [LICENSE](LICENSE) for details.

