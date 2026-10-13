const BASE = import.meta.env.VITE_MCP_URL || 'http://localhost:8000'

export type ToolCall = {
  name: string
  args?: Record<string, unknown>
  status: 'pending' | 'success' | 'error'
  durationMs?: number
  result?: unknown
  error?: string
  timestamp: string
}

async function callTool(name: string, args: Record<string, unknown> = {}): Promise<unknown> {
  const res = await fetch(`${BASE}/tools/${name}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(args),
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`Tool ${name} failed: ${res.status} ${text}`)
  }
  return res.json()
}

export const mcp = {
  getTrip: (tripId = 'TRIP-100') => callTool('get_trip', { trip_id: tripId }),
  checkFlightStatus: (tripId = 'TRIP-100') => callTool('check_flight_status', { trip_id: tripId }),
  getPreferences: (userId = 'user-alex') => callTool('get_preferences', { user_id: userId }),
  searchAlternatives: () => callTool('search_alternatives', {}),
  proposeRescuePlan: (selectedFlightId: string) =>
    callTool('propose_rescue_plan', { selected_flight_id: selectedFlightId }),
  savePreference: (key: string, value: unknown) =>
    callTool('save_preference', { key, value }),
  approveRescuePlan: (planId: string, planHash: string) =>
    callTool('approve_rescue_plan', { plan_id: planId, plan_hash: planHash }),
  executeRescuePlan: (planId: string, forceFailStep?: string) =>
    callTool('execute_rescue_plan', {
      plan_id: planId,
      ...(forceFailStep ? { force_fail_step: forceFailStep } : {}),
    }),
  getPlanStatus: (planId: string) => callTool('get_plan_status', { plan_id: planId }),
}
