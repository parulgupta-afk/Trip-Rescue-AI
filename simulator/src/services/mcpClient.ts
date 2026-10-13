const BASE = import.meta.env.VITE_MCP_URL || 'http://localhost:8000'

export type ToolCall = {
  name: string
  status: 'pending' | 'success' | 'error'
  durationMs?: number
  result?: unknown
  error?: string
  timestamp: string
}

async function callTool(name: string, args: Record<string, unknown> = {}): Promise<any> {
  const res = await fetch(`${BASE}/tools/${name}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(args),
  })
  if (!res.ok) throw new Error(`Tool ${name} failed: ${res.status} ${await res.text()}`)
  return res.json()
}

export const mcp = {
  getTrip: () => callTool('get_trip'),
  checkFlightStatus: () => callTool('check_flight_status'),
  getPreferences: () => callTool('get_preferences'),
  listPreferences: () => callTool('list_preferences'),
  searchAlternatives: () => callTool('search_alternatives'),
  proposeRescuePlan: (id: string) => callTool('propose_rescue_plan', { selected_flight_id: id }),
  savePreference: (key: string, value: unknown) => callTool('save_preference', { key, value }),
  approveRescuePlan: (planId: string, planHash: string) =>
    callTool('approve_rescue_plan', { plan_id: planId, plan_hash: planHash }),
  executeRescuePlan: (planId: string, forceFailStep?: string) =>
    callTool('execute_rescue_plan', {
      plan_id: planId,
      ...(forceFailStep ? { force_fail_step: forceFailStep } : {}),
    }),
  getPlanStatus: (planId: string) => callTool('get_plan_status', { plan_id: planId }),
  draftNotifications: (planId: string) => callTool('draft_notifications', { plan_id: planId }),
  sendNotifications: (planId: string, approved = true) =>
    callTool('send_notifications', { plan_id: planId, approved }),
}
