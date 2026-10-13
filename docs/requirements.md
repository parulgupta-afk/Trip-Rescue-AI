# Requirements Validation (Phase 0)

**Date:** 2026-10-13  
**Hackathon:** Alexa+ Track (target deadline ~2026-10-23/24)

## Judging Criteria Mapping

| Criterion              | Weight | Our Deliverable |
|------------------------|--------|-----------------|
| Tech Implementation    | Equal  | Real MCP server (Streamable HTTP), typed tools, structured outputs, Agent Skill, MCP Apps cards, real tool-call logs |
| Design                 | Equal  | Traveller-centric UI: disruption card, ranked alternatives, approval card, execution status, updated itinerary |
| Potential Impact       | Equal  | Multi-service coordination burden reduction for frequent/business travellers |
| Quality of the Idea    | Equal  | Full recovery workflow with approval-bound execution, rollback, memory |
| Friction-log bonus     | Bonus  | docs/friction-log.md with genuine issues |

## Confirmed MVP Scope (P0 only)

1. Disruption detection
2. Alternative search + ranking
3. Rescue-plan generation
4. Approval gate (hash-bound)
5. Execution + rollback
6. Persistent preferences
7. Browser simulator with real MCP calls

## Explicitly Deferred

- Real airline/hotel/ride APIs
- Real payments / SMS / email
- Native mobile / advanced voice
- Multiple disruption scenarios beyond 4h delay + provider failure
- Family accounts

## Open Questions (to verify on official page)

- Exact MCP protocol version required (target 2025-11-25)
- Whether MCP Apps / elicitation are mandatory or optional
- Alexa+ CLI / credential availability
- AWS Builder / Open Source mini-challenge eligibility
- Submission format (repo + video length limits)

Record any changes here as they are confirmed.
