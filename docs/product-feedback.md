# Product Feedback (for friction / platform notes)

## What worked well
- Clear separation of propose vs commit tools makes safety enforceable in the server.
- Deterministic mock providers let us demo approval, failure, and memory reliably.
- Plan-hash binding is easy to explain to judges and hard to fake.

## What was harder
- Full MCP client in the browser is heavier than a thin HTTP facade for a hackathon simulator.
- Optional host features (MCP Apps cards, elicitation) may not be available in every environment—core workflow must work without them.
- Balancing “agent feels smart” with “never claim a booking is confirmed” needs careful skill text.

## Suggestions for the platform
- First-class Streamable HTTP examples with typed structured outputs.
- Document which MCP extensions Alexa+ hosts actually support.
- Faster path from “empty repo” to “one tool callable from a web client.”

## If we had more time
- Live Bedrock/Strands orchestration with the same tools
- Real Alexa+ skill packaging via official CLI
- Second disruption scenario (cancellation)
- Stronger MCP Apps UI cards when the host supports them
