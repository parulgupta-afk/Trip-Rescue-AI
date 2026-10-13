# Architecture

## High-Level Flow

Traveller → Simulator / Alexa+ → Agent Skill → MCP Client → Streamable HTTP → MCP Server

MCP Server contains:
- Tool Registry (11 tools, tiered read / propose / commit)
- Validation (Pydantic)
- Authorization & Approval Service (hash + expiry + ownership)
- Plan Engine (versioned, deterministic)
- Execution Service (saga-style, idempotent)
- Rollback / Compensation
- Provider Layer (mock Flight / Hotel / Ride / Message)
- SQLite persistence

## Tool Tiers

**Tier A – Read (safe, retryable)**  
`get_trip`, `check_flight_status`, `get_preferences`, `search_alternatives`, `get_plan_status`

**Tier B – Propose (no side-effects)**  
`propose_rescue_plan`, `draft_notifications`, `save_preference`

**Tier C – Commit (require valid approval)**  
`approve_rescue_plan`, `execute_rescue_plan`, `send_notifications`

## Plan-Hash Binding

1. Generate canonical plan JSON (actions + costs + targets)
2. `plan_hash = SHA256(canonical)`
3. Approval records the hash
4. Execution re-verifies hash, ownership, expiry, status before any provider call

## Failure Model

Saga-style:
- Forward operation + success check + compensating action (where possible)
- States: PENDING → APPROVED → EXECUTING → SUCCEEDED | FAILED_ROLLED_BACK | PARTIALLY_FAILED | CANCELLED
- Notifications are irreversible → executed last

## Deterministic Demo Mode

Same MCP tools + same application state, controlled conversation sequence.  
Never uses prerecorded tool results.
