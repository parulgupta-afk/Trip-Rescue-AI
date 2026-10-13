# Product Description (for submission form)

## One-liner
Trip Rescue AI recovers a disrupted trip—flights, hotel, ride, and notifications—in one approval-driven agent workflow.

## Problem
A single delayed flight cascades: missed connections, invalid hotel check-ins, wrong pickup times, and people waiting. Travellers must coordinate multiple services under stress. Chatbots explain options; they rarely coordinate and execute safely.

## Solution
The user says: “My flight is delayed. Fix my trip.”

Trip Rescue AI:
1. Detects the disruption and downstream impact
2. Ranks alternatives against saved preferences
3. Builds one multi-service rescue plan
4. Requires explicit approval of the exact plan (cryptographic hash)
5. Executes only the approved version, with rollback on failure
6. Drafts notifications for a second approval before send
7. Remembers preferences for the next trip

## Differentiation
- **Coordination, not search** – one plan across flight, hotel, ride, notifications
- **Approval that cannot be bypassed** – server enforces plan-hash binding
- **Honest failure handling** – saga-style compensation; irreversible actions never “undone”
- **Persistent memory** – preferences change ranking next time
- **Real MCP tools** – discoverable, typed, tested; simulator calls the live server

## Tech highlights
- Official MCP Python SDK + Streamable HTTP
- 12 tools (read / propose / commit tiers)
- SQLite-backed plans, approvals, audit steps
- React simulator with live tool-call log
- Agent Skill (`SKILL.md`) + deterministic demo orchestrator
- Docker + GitHub Actions CI

## What is simulated
Mock flight/hotel/ride/message providers with realistic interfaces. No real airline bookings or payments.

## Impact
Reduces coordination burden for frequent and business travellers when one disruption affects many bookings and people—at any hour.
