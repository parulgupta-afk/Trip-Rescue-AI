# Friction Log

Genuine issues only.

---

## 2026-10-13 – Project bootstrap
- **Trying:** Create monorepo (Python MCP + React simulator).
- **Happened:** Clean scaffold; SQLite path needed `/tmp` in sandbox (disk I/O on default path).
- **Expected:** Local relative DB path to work everywhere.
- **Severity:** low
- **Workaround:** Configurable DB path (`/tmp/trip_rescue.db` in constrained environments).
- **Suggestion:** Document recommended writable paths for ephemeral runners.

## 2026-10-13 – MCP browser client vs facade
- **Trying:** Drive tools from a React simulator.
- **Happened:** Full Streamable HTTP MCP client in browser adds complexity for a 10-day hackathon.
- **Expected:** Lightweight way to call the same tools the MCP server exposes.
- **Severity:** medium
- **Workaround:** FastAPI HTTP facade that invokes the same tool functions the MCP server registers; MCP server remains the real protocol surface.
- **Suggestion:** Official thin HTTP bridge or browser-friendly MCP client examples.

## 2026-10-13 – Optional host features
- **Trying:** Plan for MCP Apps cards and Alexa+ host integration.
- **Happened:** Host support for optional extensions is uncertain until credentials/CLI are available.
- **Expected:** Clear matrix of required vs optional capabilities per track.
- **Severity:** medium
- **Workaround:** Core workflow works with plain tool calls + simulator cards; treat MCP Apps / Alexa+ as add-ons.
- **Suggestion:** Publish a support matrix for protocol version, Apps, Skills, and transport per host.
