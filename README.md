# Trip Rescue AI

**One request. One coordinated recovery. You're always in control.**

Alexa+ Hackathon project — an AI agent that recovers disrupted trips across flights, hotels, rides and notifications with explicit user approval before any consequential action.

## Problem

A delayed flight can cascade: missed connections, invalid hotel check-ins, wrong pickup times, people waiting. Travellers are forced to coordinate multiple services under stress.

## Solution

User says: *"Alexa, my flight is delayed. Fix my trip."*

Trip Rescue AI:

1. Retrieves the itinerary and detects consequences
2. Searches & ranks alternatives against saved preferences
3. Builds a complete multi-service rescue plan
4. Requires explicit approval of the exact plan (hash-bound)
5. Executes only the approved version with rollback on failure
6. Remembers preferences for the next trip

## Architecture (High Level)

```
Traveller → Alexa+ / Browser Simulator
                ↓
           Agent Skill
                ↓
           MCP Client  ──Streamable HTTP──►  MCP Server (Python)
                                              ├── Tool Registry
                                              ├── Plan Engine
                                              ├── Approval Service
                                              └── Mock Providers (Flight/Hotel/Ride/Message)
                                                    ↓
                                               SQLite
```

## Tech Stack

| Layer        | Technology                          |
|--------------|-------------------------------------|
| Frontend     | React + TypeScript + Vite           |
| Backend      | Python 3.12 + Official MCP SDK      |
| Transport    | Streamable HTTP                     |
| Database     | SQLite                              |
| Validation   | Pydantic                            |
| Testing      | pytest + Playwright                 |

## Quick Start (Windows)

```powershell
# Clone
git clone https://github.com/<you>/trip-rescue.git
cd trip-rescue

# Backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
uvicorn server.app:app --reload --port 8000

# Frontend (new terminal)
cd simulator
npm install
npm run dev
```

Open http://localhost:5173

## Demo Scenario

Fictional traveller **Alex** (Delhi → New York) has a 4-hour delay on the first leg. The agent detects impact on connection, hotel and airport pickup, proposes ranked alternatives, builds a full recovery plan, waits for approval, executes, and saves preferences.

## Safety Guarantees

- Plan generation ≠ execution
- Approval is bound to a cryptographic plan hash
- Stale / modified / expired approvals are rejected
- Idempotent execution
- Compensating actions on partial failure
- Server (not LLM) enforces authorization

## Project Status (Phases 0–3 Complete)

- [x] Phase 0 – Requirements & scaffold
- [x] Phase 1 – MCP vertical slice
- [x] Phase 2 – Data model + mock providers
- [x] Phase 3 – Rescue-plan engine
- [ ] Phase 4 – Approval + execution + rollback
- [ ] Phase 5 – Memory + notifications + full journey
- [ ] Phase 6 – Agent Skill + MCP Apps
- [ ] Phase 7 – Deployment & QA
- [ ] Phase 8–9 – Demo & submission

## License

MIT
